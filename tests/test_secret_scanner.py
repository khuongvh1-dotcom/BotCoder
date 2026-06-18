from src.security.secret_scanner import scan, scan_text


def test_detects_anthropic_key():
    hits = scan_text("ANTHROPIC_API_KEY=sk-ant-abc123456789", "config.py")
    assert any(h.rule == "anthropic_api_key" for h in hits)


def test_detects_private_key_block():
    hits = scan_text("-----BEGIN RSA PRIVATE KEY-----", "id_rsa")
    assert any(h.rule == "private_key_block" for h in hits)


def test_detects_github_pat_and_openai():
    hits = scan_text("token = ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ012345", "x.py")
    assert any(h.rule == "github_pat" for h in hits)
    hits2 = scan_text("key='sk-ABCDEFGHIJKLMNOPQRSTUV'", "y.py")
    assert any(h.rule in ("openai_key", "generic_secret_assign") for h in hits2)


def test_redacts_snippet():
    hits = scan_text("ANTHROPIC_API_KEY=sk-ant-supersecretvalue", "c.py")
    assert "supersecret" not in hits[0].snippet
    assert "***" in hits[0].snippet


def test_clean_text_no_hits():
    assert scan_text("def add(a, b):\n    return a + b\n", "calc.py") == []


def test_scan_files_and_forbidden_env(tmp_path):
    (tmp_path / "calc.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    (tmp_path / ".env").write_text("ANTHROPIC_API_KEY=sk-ant-zzz", encoding="utf-8")
    hits = scan(["calc.py", ".env"], workspace=tmp_path)
    rules = {h.rule for h in hits}
    assert "forbidden_file" in rules        # .env flagged by name
    assert all(h.file != "calc.py" for h in hits)
