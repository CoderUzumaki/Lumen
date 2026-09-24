"""Invoice upload pipeline: POST /extract -> vision OCR -> normalize -> save.

The vision model is always mocked; these tests spend no OpenRouter requests.
"""
import io

import pytest
from PIL import Image, ImageDraw

AUTH = {"Authorization": "Bearer x.y.z"}

# Shaped like the vision model's reply for the synthetic Sharma Office Supplies
# invoice (amounts as strings with "Rs", quantities as strings or ints).
SHARMA_OCR = {
    "invoice_number": "INV-20931",
    "vendor_name": "Sharma Office Supplies Pvt Ltd",
    "date": "2026-09-14",
    "total_amount": "Rs 1,121.00",
    "items": [
        {"item_name": "A4 Paper Ream", "quantity": "2", "price": "Rs 300.00"},
        {"item_name": "Stapler", "quantity": 1, "price": "Rs 350.00"},
    ],
    "customer_name": "Lumen Test Co",
    "address": "12 MG Road, Pune",
    "payment_method": "UPI",
    "tax_amount": "Rs 171.00",
    "category": "Shopping",
}


# --- normalize ------------------------------------------------------------


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("Rs 1,121.00", 1121.0),
        ("Rs. 1,121.00", 1121.0),
        ("INR 1,121.00", 1121.0),
        ("₹1,12,100", 112100.0),
        ("$12.50", 12.5),
        ("1121.00 INR", 1121.0),
        (1121, 1121.0),
        (12.5, 12.5),
        ("", None),
        ("N/A", None),
        (None, None),
    ],
)
def test_clean_amount(raw, expected):
    from utils.normalize import clean_amount

    assert clean_amount(raw) == expected


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("2026-09-14", "2026-09-14"),
        ("2026-09-14T10:30:00", "2026-09-14"),
        ("14/09/2026", "2026-09-14"),
        ("14-09-2026", "2026-09-14"),
        ("04/09/2026", "2026-09-04"),  # day-first, as on Indian invoices
        ("Sep 14, 2026", "2026-09-14"),
        ("14 September 2026", "2026-09-14"),
        ("14 Sep", None),  # no year: don't invent one
        ("not a date", None),
        ("null", None),
        (None, None),
    ],
)
def test_parse_date_returns_iso_or_none(raw, expected):
    from utils.normalize import parse_date

    assert parse_date(raw) == expected


def test_normalize_sharma_invoice():
    from utils.normalize import normalize_transaction

    n = normalize_transaction(SHARMA_OCR)
    assert n["vendor_name"] == "Sharma Office Supplies Pvt Ltd"
    assert n["invoice_number"] == "INV-20931"
    assert n["date"] == "2026-09-14"
    assert n["total_amount"] == 1121.0
    assert n["tax_amount"] == 171.0
    assert n["payment_method"] == "UPI"
    assert n["items"] == [
        {"item_name": "A4 Paper Ream", "quantity": 2, "unit_price": 300.0, "total_price": 600.0},
        {"item_name": "Stapler", "quantity": 1, "unit_price": 350.0, "total_price": 350.0},
    ]


def test_normalize_survives_sparse_and_odd_model_output():
    from utils.normalize import normalize_transaction

    n = normalize_transaction(
        {
            "vendor_name": "null",
            "customer_name": "  Corner Store ",
            "invoice_number": "",
            "total_amount": "Total: Rs 250",
            "date": "garbage",
            "category": None,
            "payment_method": None,
            "items": [
                {"item_name": "Milk", "quantity": "2 pcs", "price": "Rs 30"},
                {"item_name": "Bread", "price": None},
                {"item_name": None, "price": None},  # nothing usable: dropped
                "not an item",
            ],
        }
    )
    assert n["vendor_name"] == "Corner Store"
    assert n["invoice_number"] is None
    assert n["total_amount"] == 250.0
    assert n["date"] is None
    assert n["category"] == "Other"
    assert n["payment_method"] == "Unknown"
    assert n["items"] == [
        {"item_name": "Milk", "quantity": 2, "unit_price": 30.0, "total_price": 60.0},
        {"item_name": "Bread", "quantity": 1, "unit_price": None, "total_price": None},
    ]


@pytest.mark.parametrize("items", [None, "none", {}, []])
def test_normalize_items_not_a_list(items):
    from utils.normalize import normalize_transaction

    assert normalize_transaction({"total_amount": "10", "items": items})["items"] == []


# --- vision call ------------------------------------------------------------


class _FakeResponse:
    def __init__(self, status, body):
        self.status_code = status
        self._body = body
        self.text = str(body)

    def json(self):
        return self._body


def _reply(content):
    return _FakeResponse(200, {"choices": [{"message": {"content": content}}]})


@pytest.mark.parametrize(
    "content",
    [
        '{"vendor_name": "A"}',
        '```json\n{"vendor_name": "A"}\n```',
        'Here is the extracted data:\n{"vendor_name": "A"}',
    ],
)
def test_parse_json_reply_accepts_wrapped_json(content):
    from utils.openrouter import parse_json_reply

    assert parse_json_reply(content) == {"vendor_name": "A"}


@pytest.mark.parametrize("content", ["I cannot read this image.", "{not json}", "[1, 2]"])
def test_parse_json_reply_rejects_non_objects(content):
    from utils.llm import LLMError
    from utils.openrouter import parse_json_reply

    with pytest.raises(LLMError) as excinfo:
        parse_json_reply(content)
    assert excinfo.value.kind == LLMError.BAD_RESPONSE


@pytest.mark.parametrize(
    "status, body, kind",
    [
        (401, {"error": {"message": "User not found.", "code": 401}}, "auth"),
        (429, {"error": {"message": "Rate limit exceeded", "code": 429}}, "rate_limited"),
        (404, {"error": {"message": "No endpoints found", "code": 404}}, "config"),
    ],
)
def test_vision_call_raises_typed_errors(monkeypatch, status, body, kind):
    from utils import llm
    from utils.openrouter import extract_and_structure_with_openrouter

    calls = []

    def post(*a, **k):
        calls.append(1)
        return _FakeResponse(status, body)

    monkeypatch.setattr(llm.requests, "post", post)
    with pytest.raises(llm.LLMError) as excinfo:
        extract_and_structure_with_openrouter("aGk=", "image/png")
    assert excinfo.value.kind == kind
    assert len(calls) == 1  # fatal errors are not retried: each try costs quota


def test_vision_call_sends_image_and_retries_unparseable_reply(monkeypatch):
    monkeypatch.setenv("LLM_VISION_MODEL", "vision/primary:free")
    monkeypatch.setenv("LLM_VISION_FALLBACK_MODELS", "vision/backup:free,openrouter/free")
    from utils import llm
    from utils.openrouter import extract_and_structure_with_openrouter

    sent = []
    replies = iter([_reply("Sorry, the image is blurry."), _reply('{"vendor_name": "A"}')])

    def post(url, headers, json, timeout):
        sent.append(json)
        return next(replies)

    monkeypatch.setattr(llm.requests, "post", post)
    assert extract_and_structure_with_openrouter("aGk=", "image/png") == {"vendor_name": "A"}
    assert len(sent) == 2
    assert sent[0]["models"] == ["vision/primary:free", "vision/backup:free", "openrouter/free"]
    parts = sent[0]["messages"][0]["content"]
    assert parts[1] == {"type": "image_url", "image_url": {"url": "data:image/png;base64,aGk="}}


# --- POST /extract ------------------------------------------------------------


def _png_bytes():
    img = Image.new("RGB", (400, 300), "white")
    ImageDraw.Draw(img).text((20, 20), "Sharma Office Supplies  INV-20931  Rs 1,121.00", fill="black")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _pdf_bytes(pages=1):
    imgs = [Image.new("RGB", (400, 300), "white") for _ in range(pages)]
    buf = io.BytesIO()
    imgs[0].save(buf, format="PDF", save_all=True, append_images=imgs[1:])
    return buf.getvalue()


def _upload(client, content, name="invoice.png"):
    return client.post(
        "/extract",
        data={"file": (io.BytesIO(content), name)},
        headers=AUTH,
        content_type="multipart/form-data",
    )


@pytest.fixture
def client(authed_client, monkeypatch):
    """Signed-in client with no rate limit and an empty database."""
    from app import app
    from models import Transaction, TransactionItem, User
    from models.database import db
    from utils.limiter import limiter

    monkeypatch.setattr(limiter, "enabled", False)
    with app.app_context():
        db.session.query(TransactionItem).delete()
        db.session.query(Transaction).delete()
        db.session.query(User).delete()
        db.session.commit()
    return authed_client


@pytest.fixture
def ocr(monkeypatch):
    """Replace the vision call; `ocr.result` is what it returns, `ocr.calls` what it got."""
    import routes.ocr

    class Fake:
        def __init__(self):
            self.result = dict(SHARMA_OCR)
            self.calls = []

        def __call__(self, image_base64, media_type):
            self.calls.append(media_type)
            if isinstance(self.result, Exception):
                raise self.result
            return dict(self.result)

    fake = Fake()
    monkeypatch.setattr(routes.ocr, "extract_and_structure_with_openrouter", fake)
    return fake


def _rows():
    from app import app
    from models import Transaction

    with app.app_context():
        return Transaction.query.filter_by(user_id="user-1").all()


def test_extract_requires_auth():
    from app import app

    resp = app.test_client().post("/extract")
    assert resp.status_code == 401


def test_extract_image_saves_and_shows_everywhere(client, ocr):
    resp = _upload(client, _png_bytes())
    assert resp.status_code == 200, resp.get_json()
    body = resp.get_json()
    assert body["success"] and body["duplicate"] is False
    assert body["data"]["total_amount"] == 1121.0
    assert ocr.calls == ["image/png"]

    # Dashboard list
    listed = client.get("/transactions", headers=AUTH).get_json()
    [tx] = [t for t in listed["data"] if t["id"] == body["transaction_id"]]
    assert tx["vendor_name"] == "Sharma Office Supplies Pvt Ltd"
    assert tx["date"] == "2026-09-14"
    assert tx["total_amount"] == 1121.0

    # Analytics (month is 0-based: 8 = September)
    summary = client.get(
        "/analytics/summary?time_range=monthly&year=2026&month=8", headers=AUTH
    )
    assert summary.status_code == 200
    assert "1121" in summary.get_data(as_text=True)

    # Ask Lumen's SQL step reads the same database
    import routes.chat

    result = routes.chat.engine.sql_agent.execute_sql(
        "SELECT COALESCE(SUM(total_amount), 0) AS total FROM transactions WHERE user_id = 'user-1'",
        "user-1",
    )
    assert result["data"] == [{"total": 1121.0}]


def test_extract_creates_local_user_row_for_foreign_key(client, ocr):
    # Postgres enforces transactions.user_id -> users.id; SQLite doesn't, so
    # check the row directly.
    from app import app
    from models import User
    from models.database import db

    assert _upload(client, _png_bytes()).status_code == 200
    with app.app_context():
        user = db.session.get(User, "user-1")
        assert user is not None and user.email == "u@example.com"


def test_reupload_is_reported_as_duplicate(client, ocr):
    first = _upload(client, _png_bytes()).get_json()
    second = _upload(client, _png_bytes()).get_json()
    assert second["duplicate"] is True
    assert second["transaction_id"] == first["transaction_id"]
    assert second["message"] == "This invoice was already uploaded"
    assert len(_rows()) == 1


def test_receipts_without_invoice_number_are_not_deduplicated(client, ocr):
    ocr.result = {"vendor_name": "Chai Point", "total_amount": "Rs 40", "invoice_number": None}
    first = _upload(client, _png_bytes()).get_json()
    ocr.result = {"vendor_name": "Chai Point", "total_amount": "Rs 60", "invoice_number": None}
    second = _upload(client, _png_bytes()).get_json()
    assert second["duplicate"] is False
    assert first["transaction_id"] != second["transaction_id"]
    assert sorted(t.total_amount for t in _rows()) == [40.0, 60.0]


@pytest.mark.parametrize(
    "kind, status, code",
    [
        ("auth", 503, "llm_unavailable"),  # never 401: that signs the user out
        ("insufficient_credits", 503, "llm_unavailable"),
        ("config", 503, "llm_unavailable"),
        ("unavailable", 503, "llm_unavailable"),
        ("rate_limited", 429, "llm_rate_limited"),
        ("bad_response", 502, "llm_bad_response"),
    ],
)
def test_ocr_failures_are_clear_errors(client, ocr, kind, status, code):
    from utils.llm import LLMError

    ocr.result = LLMError(kind, "OpenRouter HTTP 401: User not found. key sk-or-...dc68")
    resp = _upload(client, _png_bytes())
    assert resp.status_code == status
    body = resp.get_json()
    assert body["code"] == code
    assert "User not found" not in body["error"] and "dc68" not in body["error"]
    assert _rows() == []


def test_unexpected_ocr_exception_is_generic_500(client, ocr):
    ocr.result = RuntimeError("boom")
    resp = _upload(client, _png_bytes())
    assert resp.status_code == 500
    assert resp.get_json()["code"] == "extract_failed"


def test_image_with_no_invoice_data_is_422(client, ocr):
    ocr.result = {"vendor_name": None, "total_amount": None, "items": None}
    resp = _upload(client, _png_bytes())
    assert resp.status_code == 422
    assert resp.get_json()["code"] == "no_invoice_data"
    assert _rows() == []


def test_save_failure_is_an_error_not_a_silent_success(client, ocr, monkeypatch):
    import routes.ocr

    def broken(*a, **k):
        raise RuntimeError("database is locked")

    monkeypatch.setattr(routes.ocr, "save_transaction_detailed", broken)
    resp = _upload(client, _png_bytes())
    assert resp.status_code == 500
    body = resp.get_json()
    assert body["code"] == "save_failed"
    assert "locked" not in body["error"]


@pytest.mark.parametrize("pages", [1, 3])
def test_pdf_first_page_is_rendered_without_poppler(client, ocr, pages):
    resp = _upload(client, _pdf_bytes(pages), name="invoice.pdf")
    assert resp.status_code == 200, resp.get_json()
    body = resp.get_json()
    assert body["ocr_data"]["pages_processed"] == 1
    assert body["ocr_data"]["total_pages"] == pages
    assert ocr.calls == ["image/png"]


def test_corrupt_pdf_is_422(client, ocr):
    resp = _upload(client, b"%PDF-1.4 this is not really a pdf", name="invoice.pdf")
    assert resp.status_code == 422
    assert resp.get_json()["code"] == "pdf_unreadable"
    assert ocr.calls == []


def test_unsupported_extension_is_400(client, ocr):
    resp = _upload(client, b"hello", name="invoice.txt")
    assert resp.status_code == 400
    assert ocr.calls == []
