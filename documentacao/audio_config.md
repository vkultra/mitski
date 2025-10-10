# Configuração de Áudios nos Bots Secundários

Este documento explica como funciona a configuração de respostas a mensagens de áudio/voz nos bots secundários. O recurso permite escolher entre uma resposta fixa ou a transcrição automática via Whisper.

## Visão Geral

- A configuração é feita diretamente no bot gerenciador (`/start → 🤖 IA → ⚡ Ações`).
- A linha **Audios | Configurar** aparece abaixo de `/start | Configurar`.
- Qualquer usuário do bot gerenciador pode definir as preferências dos próprios bots. Cada usuário possui configurações isoladas que valem para todos os bots cadastrados por ele.
- Opções disponíveis:
  - **Resposta padrão fixa**: texto enviado imediatamente quando o usuário mandar um áudio.
  - **Transcrição via Whisper**: as mensagens de áudio são transcritas e encaminhadas para a IA (Grok) como se fossem texto enviado pelo usuário.

## Fluxo de Uso

1. Abra o bot gerenciador e toque em **🤖 IA**.
2. Escolha o bot desejado.
3. No menu **⚡ Ações**, selecione **Audios → Configurar**.
4. Use os botões (Whisper vem ativo por padrão para novos usuários):
   - `Ativar Whisper` / `Usar resposta padrão` para alternar o modo.
   - `Editar resposta padrão` para definir o texto enviado no modo padrão.

## Variáveis de Ambiente

Configure os valores abaixo no arquivo `.env` para habilitar o Whisper:

```
WHISPER_API_KEY=seu_token_whisper
WHISPER_API_BASE=https://api.openai.com/v1
WHISPER_MODEL=whisper-1
WHISPER_TIMEOUT=15
AUDIO_MAX_DURATION=180
AUDIO_MAX_SIZE_MB=20
FFMPEG_BINARY=ffmpeg
```

- `WHISPER_API_KEY` é obrigatório para transcrever. O menu não exibe se a chave está configurada.
- `AUDIO_MAX_DURATION` e `AUDIO_MAX_SIZE_MB` definem os limites para rejeição silenciosa de áudios muito longos ou pesados.
- `FFMPEG_BINARY` aponta para o executável usado na conversão de áudio para voice.

## Rate Limits

Atualize `RATE_LIMITS_JSON` para incluir limites dedicados:

```
{"audio:upload":{"limit":10,"window":60},"audio:config":{"limit":6,"window":60}}
```

Além disso, existe um cooldown interno de 2 segundos para alterações rápidas na configuração.

## Comportamento em Tempo de Execução

- O processamento de áudio é totalmente assíncrono (fila Celery `audio`).
- Para o modo padrão, o usuário recebe apenas a resposta configurada. Sem mensagens adicionais.
- Para o modo Whisper:
  - A mensagem é baixada do Telegram, enviada ao Whisper e o texto resultante é encaminhado ao pipeline da IA.
  - Em caso de erro (ex.: sem API key, timeout, limites excedidos), nada é enviado ao usuário final. O incidente é logado e o fluxo termina silenciosamente.
- Transcrições são armazenadas em cache por 24 horas, evitando chamadas repetidas ao Whisper para o mesmo arquivo (`file_unique_id`).

## Conversão obrigatória para Voice

- Qualquer mídia cadastrada como `audio` pelo administrador é reprocessada como voice note (`sendVoice`).
- A conversão usa `ffmpeg` (configurável via `FFMPEG_BINARY`) para gerar arquivo `.ogg` com codec Opus.
- Após a primeira entrega, o `file_id` da versão voice fica em cache (`MediaFileCacheRepository`), evitando novas conversões.
- O typing effect passa a assumir `upload_voice`, garantindo consistência na experiência do usuário.
- Falhas ao converter são logadas e bloqueiam o envio do bloco até o problema ser corrigido (ex.: ffmpeg ausente).

## Observabilidade

- Logs estruturados informam duração, tamanho do arquivo, modo em uso e falhas de transcrição.
- Métricas recomendadas:
  - `audio_received_total{type="voice"}`
  - `audio_transcribed_total`
  - `audio_fail_total{reason="timeout|size|duration|whisper"}`
  - `audio_task_duration_seconds`

## Boas Práticas

- Garanta que o Whisper esteja disponível antes de alternar o modo em produção.
- Documente para o time os limites de duração/tamanho adotados.
- Monitore a fila `audio` e configure alertas para crescimento anormal.
- Valide periodicamente se o texto padrão atende ao tom desejado.

## Referências Rápidas

- Task Celery: `workers.audio_tasks.process_audio_message`
- Serviço de preferências: `services.audio.preferences_service`
- Menu de configurações: `handlers.ai.audio_menu_handlers`
