"""
Testes para identificar bugs no sistema de Recuperação.
Este arquivo contém testes específicos para reproduzir e validar problemas conhecidos.
"""

import asyncio
import gc
import time
import weakref
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from core.recovery import (
    clear_episode,
    compute_next_occurrence,
    current_episode,
    generate_episode_id,
    get_inactivity_version,
    mark_user_activity,
    parse_schedule_expression,
    try_allocate_episode,
)
from database.recovery import (
    RecoveryBlockRepository,
    RecoveryCampaignRepository,
    RecoveryStepRepository,
)
from database.recovery.delivery_repo import RecoveryDeliveryRepository
from services.recovery.sender import RecoveryMessageSender
from workers.recovery_scheduler import check_inactive, schedule_inactivity_check
from workers.recovery_sender import send_recovery_step
from workers.recovery_utils import ensure_scheduled_delivery


class TestMemoryLeaks:
    """Testes para verificar memory leaks no sistema."""

    async def test_auto_delete_task_memory_leak(self):
        """
        BUG: Tasks de auto-delete não são rastreadas, causando memory leak.
        Localização: services/recovery/sender.py, linha 74
        """
        print("\n=== TESTE 1: Memory Leak em Auto-Delete Tasks ===")

        # Monitorar tasks criadas
        created_tasks = []
        original_create_task = asyncio.create_task

        def track_create_task(coro):
            task = original_create_task(coro)
            created_tasks.append(weakref.ref(task))
            return task

        with patch("asyncio.create_task", side_effect=track_create_task):
            sender = RecoveryMessageSender("fake_token")

            # Criar blocks com auto-delete
            blocks = []
            for i in range(100):  # Simular muitas mensagens
                block = MagicMock()
                block.text = f"Mensagem {i}"
                block.media_file_id = None
                block.delay_seconds = 0
                block.auto_delete_seconds = 5  # Auto-delete ativo
                block.parse_mode = "Markdown"
                blocks.append(block)

            # Mock da API do Telegram
            with patch.object(
                sender.telegram_api,
                "send_message",
                return_value={"result": {"message_id": 123}},
            ):
                await sender.send_blocks(blocks, chat_id=123456, preview=False)

        # Verificar tasks criadas
        print(f"Tasks criadas: {len(created_tasks)}")

        # Forçar garbage collection
        gc.collect()

        # Verificar quantas tasks ainda estão na memória
        alive_tasks = sum(1 for ref in created_tasks if ref() is not None)
        print(f"Tasks ainda na memória após GC: {alive_tasks}")

        # RESULTADO ESPERADO: Todas as tasks deveriam ser coletadas pelo GC
        # BUG CONFIRMADO SE: alive_tasks == 100 (tasks não são liberadas)

        return {
            "bug_detected": alive_tasks > 50,
            "tasks_created": len(created_tasks),
            "tasks_leaked": alive_tasks,
        }


class TestTimezoneInconsistency:
    """Testes para verificar inconsistências de timezone."""

    async def test_datetime_utcnow_usage(self):
        """
        BUG: Uso de datetime.utcnow() ao invés de datetime.now(timezone.utc)
        Localização: workers/recovery_sender.py, linha 187
        """
        print("\n=== TESTE 2: Inconsistência de Timezone ===")

        # Verificar o código fonte para datetime.utcnow()
        with open("workers/recovery_sender.py", "r") as f:
            content = f.read()

        # Procurar por uso incorreto
        utcnow_found = "datetime.utcnow()" in content
        line_number = None

        if utcnow_found:
            lines = content.split("\n")
            for i, line in enumerate(lines, 1):
                if "datetime.utcnow()" in line:
                    line_number = i
                    print(f"BUG ENCONTRADO na linha {i}: {line.strip()}")

        # Testar comportamento real
        from workers.recovery_sender import send_recovery_step

        # Mock para capturar o timestamp usado
        captured_timestamps = []

        async def mock_create_or_update(**kwargs):
            if "sent_at" in kwargs:
                captured_timestamps.append(kwargs["sent_at"])
            return MagicMock()

        with patch.object(
            RecoveryDeliveryRepository,
            "create_or_update",
            side_effect=mock_create_or_update,
        ):
            with patch.object(
                RecoveryDeliveryRepository, "get_delivery", return_value=None
            ):
                # Executar parte do código que usa timestamp
                # (simplificado para teste)
                pass

        # Verificar se timestamps são timezone-aware
        result = {
            "bug_detected": utcnow_found,
            "line_number": line_number,
            "uses_utcnow": utcnow_found,
            "should_use": "datetime.now(timezone.utc)",
        }

        return result


class TestRaceConditions:
    """Testes para verificar race conditions."""

    async def test_delivery_race_condition(self):
        """
        BUG: ensure_scheduled_delivery não verifica duplicatas antes de criar
        Localização: workers/recovery_utils.py
        """
        print("\n=== TESTE 3: Race Condition em Deliveries ===")

        # Configurar dados de teste
        campaign_id = 1
        bot_id = 100
        user_id = 1000
        step_id = 10
        episode_id = generate_episode_id()

        # Contador de criações
        create_count = 0

        async def mock_create(**kwargs):
            nonlocal create_count
            create_count += 1
            await asyncio.sleep(0.01)  # Simular latência do DB
            return MagicMock(id=create_count)

        # Simular chamadas concorrentes
        with patch.object(
            RecoveryDeliveryRepository, "create_or_update", side_effect=mock_create
        ):

            # Criar múltiplas tasks concorrentes
            tasks = []
            for _ in range(10):
                task = asyncio.create_task(
                    asyncio.to_thread(
                        ensure_scheduled_delivery,
                        campaign_id=campaign_id,
                        bot_id=bot_id,
                        user_db_id=user_id,
                        step_id=step_id,
                        episode_id=episode_id,
                        scheduled_for=datetime.now(timezone.utc),
                        campaign_version=1,
                    )
                )
                tasks.append(task)

            # Aguardar todas as tasks
            await asyncio.gather(*tasks, return_exceptions=True)

        print(f"Deliveries criadas: {create_count}")

        # RESULTADO ESPERADO: Apenas 1 delivery deveria ser criada
        # BUG CONFIRMADO SE: create_count > 1
        result = {
            "bug_detected": create_count > 1,
            "expected_creates": 1,
            "actual_creates": create_count,
            "duplicates": create_count - 1,
        }

        return result

    async def test_reorder_race_condition(self):
        """
        BUG: Reordenação sem lock adequado pode causar inconsistências
        Localização: database/recovery/campaign_repo.py
        """
        print("\n=== TESTE 4: Race Condition na Reordenação ===")

        # Criar campaign e steps de teste
        bot_id = 200
        campaign = await RecoveryCampaignRepository.get_or_create(bot_id)
        campaign_id = campaign.id if hasattr(campaign, "id") else campaign

        # Adicionar múltiplos steps
        steps = []
        for i in range(5):
            step = await RecoveryStepRepository.create_step(
                campaign_id, "relative", str(i * 60)
            )
            steps.append(step)

        # Função para deletar step (causa reordenação)
        async def delete_random_step():
            import random

            if steps:
                step = random.choice(steps)
                await RecoveryStepRepository.delete_step(step.id)
                steps.remove(step)

        # Executar deleções concorrentes
        tasks = []
        for _ in range(3):
            tasks.append(asyncio.create_task(delete_random_step()))

        # Aguardar com timeout para evitar deadlock
        try:
            await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True), timeout=5.0
            )
        except asyncio.TimeoutError:
            print("TIMEOUT: Possível deadlock detectado!")

        # Verificar ordenação final
        remaining_steps = await RecoveryStepRepository.list_steps(campaign_id)
        orders = [step.order_index for step in remaining_steps]

        # Verificar se há gaps ou duplicatas
        expected_orders = list(range(1, len(remaining_steps) + 1))
        is_correct = orders == expected_orders

        result = {
            "bug_detected": not is_correct,
            "final_orders": orders,
            "expected_orders": expected_orders,
            "has_gaps": max(orders) > len(orders) if orders else False,
            "has_duplicates": len(orders) != len(set(orders)),
        }

        print(f"Ordenação final: {orders}")
        print(f"Esperado: {expected_orders}")

        return result


class TestSchedulingEdgeCases:
    """Testes para edge cases de agendamento."""

    def test_same_day_past_time_scheduling(self):
        """
        BUG: Horário do mesmo dia que já passou pode não ser tratado corretamente
        Localização: core/recovery/schedule.py
        """
        print("\n=== TESTE 5: Edge Case - Horário Passado no Mesmo Dia ===")

        # Testar agendamento para "14:00" quando já são 15:00
        base_time = datetime(2025, 1, 5, 15, 0, tzinfo=timezone.utc)

        # Parse "14:00" (horário que já passou)
        definition = parse_schedule_expression("14:00")

        # Calcular próxima ocorrência
        next_occurrence = compute_next_occurrence(
            definition, base_time=base_time, timezone_name="UTC"
        )

        # Verificar se foi agendado para amanhã
        expected = datetime(2025, 1, 6, 14, 0, tzinfo=timezone.utc)
        is_correct = next_occurrence == expected

        result = {
            "bug_detected": not is_correct,
            "input_time": "14:00",
            "base_time": base_time.isoformat(),
            "computed_time": next_occurrence.isoformat(),
            "expected_time": expected.isoformat(),
            "scheduled_to_past": next_occurrence < base_time,
        }

        print(f"Base: {base_time}")
        print(f"Agendado para: {next_occurrence}")
        print(f"Esperado: {expected}")

        if next_occurrence < base_time:
            print("BUG CONFIRMADO: Agendamento para o passado!")

        return result

    def test_plus_zero_days_edge_case(self):
        """
        Teste para "+0d HH:MM" quando o horário já passou.
        """
        print("\n=== TESTE 6: Edge Case - +0d com Horário Passado ===")

        # Base: 16:00, testar "+0d 14:00"
        base_time = datetime(2025, 1, 5, 16, 0, tzinfo=timezone.utc)

        definition = parse_schedule_expression("+0d14:00")

        next_occurrence = compute_next_occurrence(
            definition, base_time=base_time, timezone_name="UTC"
        )

        # Deveria agendar para amanhã às 14:00
        expected = datetime(2025, 1, 6, 14, 0, tzinfo=timezone.utc)

        result = {
            "bug_detected": next_occurrence < base_time,
            "expression": "+0d14:00",
            "base_time": base_time.isoformat(),
            "computed_time": next_occurrence.isoformat(),
            "expected_behavior": "Should schedule for next day when time has passed",
        }

        print(f"Expressão: +0d14:00")
        print(f"Base: {base_time}")
        print(f"Agendado: {next_occurrence}")

        return result


class TestStressAndLoad:
    """Testes de carga e stress."""

    async def test_concurrent_inactivity_checks(self):
        """
        Teste de múltiplos usuários ficando inativos simultaneamente.
        """
        print("\n=== TESTE 7: Carga - Múltiplos Usuários Inativos ===")

        bot_id = 300
        num_users = 100

        # Marcar atividade para múltiplos usuários
        versions = {}
        for user_id in range(1000, 1000 + num_users):
            versions[user_id] = mark_user_activity(bot_id, user_id)

        # Simular inatividade simultânea
        start_time = time.time()

        # Mock do agendamento
        scheduled_checks = []

        def mock_apply_async(*args, **kwargs):
            scheduled_checks.append(
                {"args": args, "countdown": kwargs.get("countdown", 0)}
            )
            return MagicMock()

        with patch(
            "workers.recovery_scheduler.check_inactive.apply_async",
            side_effect=mock_apply_async,
        ):

            # Agendar verificações para todos os usuários
            for user_id in range(1000, 1000 + num_users):
                schedule_inactivity_check(bot_id, user_id, versions[user_id])

        elapsed_time = time.time() - start_time

        result = {
            "users_processed": num_users,
            "checks_scheduled": len(scheduled_checks),
            "processing_time": f"{elapsed_time:.2f}s",
            "avg_time_per_user": f"{(elapsed_time / num_users) * 1000:.2f}ms",
        }

        print(f"Usuários processados: {num_users}")
        print(f"Verificações agendadas: {len(scheduled_checks)}")
        print(f"Tempo total: {elapsed_time:.2f}s")

        return result


async def run_all_tests():
    """Executar todos os testes e gerar relatório."""
    print("\n" + "=" * 60)
    print("INICIANDO TESTES DO SISTEMA DE RECUPERAÇÃO")
    print("=" * 60)

    results = {}

    # Teste 1: Memory Leak
    try:
        test = TestMemoryLeaks()
        results["memory_leak"] = await test.test_auto_delete_task_memory_leak()
    except Exception as e:
        results["memory_leak"] = {"error": str(e)}

    # Teste 2: Timezone
    try:
        test = TestTimezoneInconsistency()
        results["timezone"] = await test.test_datetime_utcnow_usage()
    except Exception as e:
        results["timezone"] = {"error": str(e)}

    # Teste 3: Race Condition - Deliveries
    try:
        test = TestRaceConditions()
        results["delivery_race"] = await test.test_delivery_race_condition()
    except Exception as e:
        results["delivery_race"] = {"error": str(e)}

    # Teste 4: Race Condition - Reordenação
    try:
        test = TestRaceConditions()
        results["reorder_race"] = await test.test_reorder_race_condition()
    except Exception as e:
        results["reorder_race"] = {"error": str(e)}

    # Teste 5: Edge Case - Horário Passado
    try:
        test = TestSchedulingEdgeCases()
        results["past_time"] = test.test_same_day_past_time_scheduling()
    except Exception as e:
        results["past_time"] = {"error": str(e)}

    # Teste 6: Edge Case - +0d
    try:
        test = TestSchedulingEdgeCases()
        results["plus_zero_days"] = test.test_plus_zero_days_edge_case()
    except Exception as e:
        results["plus_zero_days"] = {"error": str(e)}

    # Teste 7: Stress Test
    try:
        test = TestStressAndLoad()
        results["stress_test"] = await test.test_concurrent_inactivity_checks()
    except Exception as e:
        results["stress_test"] = {"error": str(e)}

    return results


if __name__ == "__main__":
    # Executar testes
    results = asyncio.run(run_all_tests())

    # Gerar relatório
    print("\n" + "=" * 60)
    print("RELATÓRIO FINAL DE TESTES")
    print("=" * 60)

    bugs_found = []

    for test_name, result in results.items():
        print(f"\n[{test_name.upper()}]")
        if isinstance(result, dict):
            if "error" in result:
                print(f"  ❌ ERRO: {result['error']}")
            elif result.get("bug_detected"):
                print(f"  🐛 BUG DETECTADO!")
                bugs_found.append(test_name)
                for key, value in result.items():
                    if key != "bug_detected":
                        print(f"    {key}: {value}")
            else:
                print(f"  ✅ Passou")
        else:
            print(f"  Resultado: {result}")

    print("\n" + "=" * 60)
    print("RESUMO")
    print("=" * 60)
    print(f"Total de testes: {len(results)}")
    print(f"Bugs encontrados: {len(bugs_found)}")
    if bugs_found:
        print("Bugs detectados em:")
        for bug in bugs_found:
            print(f"  - {bug}")
