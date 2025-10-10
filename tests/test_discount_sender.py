import pytest

from services.offers.discount_sender import DiscountSender


def test_render_text_replaces_pix_placeholder():
    sender = DiscountSender(bot_token="dummy")

    result = sender._render_text(
        text="Pague usando {pix} agora!",
        pix_code="000PIXCODE",
        preview_mode=False,
    )

    assert result == "Pague usando 000PIXCODE agora!"


@pytest.mark.parametrize(
    "text,pix_code,preview_mode,expected",
    [
        ("Pix: {pix}", None, True, "Pix: `PREVIEW_PIX_CODE`"),
        ("Pix: {pix}", None, False, "Pix: {pix}"),
        ("Sem marcador", "ABC", False, "Sem marcador"),
    ],
)
def test_render_text_handles_preview_and_missing_pix(
    text, pix_code, preview_mode, expected
):
    sender = DiscountSender(bot_token="dummy")

    result = sender._render_text(
        text=text, pix_code=pix_code, preview_mode=preview_mode
    )

    assert result == expected
