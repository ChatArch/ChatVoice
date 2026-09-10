"""Integration edge cases discovered while wiring the Todo page."""
import json

import pytest
from chatvoice import todo_markdown


def test_refine_manual_markdown_without_summary():
    result=todo_markdown.revise_todo("", "- [ ] 整理报告", "拆细", [], lambda **kwargs: {"model":"fixture", "content":json.dumps({"content":"- [ ] 整理报告\n  - [ ] 汇总用例", "reply":"已拆解"},ensure_ascii=False)})
    assert "汇总用例" in result["content"]


def test_configuration_failure_keeps_503_without_sensitive_detail():
    class ConfigurationFailure(Exception):
        status_code=503
    def model(**kwargs):
        raise ConfigurationFailure("sensitive-config-value")
    with pytest.raises(ValueError) as error:
        todo_markdown.generate_todo("整理报告", model)
    assert getattr(error.value,"status_code",None)==503
    assert "sensitive-config-value" not in str(error.value)
