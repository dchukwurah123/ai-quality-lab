def test_reports_module_imports() -> None:
    # Guard against package-discovery regressions in CI.
    from ai_quality_lab.reports import writers

    assert hasattr(writers, "write_json_report")
    assert hasattr(writers, "write_markdown_report")
