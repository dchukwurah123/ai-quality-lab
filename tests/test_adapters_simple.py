from ai_quality_lab.adapters import case_to_request, get_adapter
from ai_quality_lab.models import EvalCase, EvalCheck, SummarizationExpected


def _case() -> EvalCase:
    return EvalCase(
        id="c1",
        task="summarization",
        input={"text": "Hello world. Extra sentence."},
        expected=SummarizationExpected("Hello world."),
        checks=[EvalCheck(type="exact_match")],
    )


def test_case_to_request() -> None:
    case = _case()
    request = case_to_request(case)
    assert request.case_id == "c1"
    assert request.task == "summarization"


def test_dataset_adapter_returns_none() -> None:
    request = case_to_request(_case())
    adapter = get_adapter("dataset")
    assert adapter.generate(request) is None


def test_echo_adapter_returns_text() -> None:
    request = case_to_request(_case())
    adapter = get_adapter("echo")
    assert adapter.generate(request) == "Hello world. Extra sentence."


def test_mock_adapter_is_deterministic() -> None:
    request = case_to_request(_case())
    adapter = get_adapter("mock")
    assert adapter.generate(request) == "Hello world"
