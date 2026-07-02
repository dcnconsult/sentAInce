"""Deploy tooling — install/uninstall must be a CLEAN, reversible, surgical round-trip: it preserves the
target's own settings (permissions / MCP / foreign hooks) and leaves no trace on uninstall."""
from exocortex import deploy


def _seed_target(tmp_path):
    """A realistic target: a git repo with a user settings.local.json (permissions + MCP + a FOREIGN hook)
    and a user .gitignore. Mirrors TAO's real shape."""
    t = tmp_path / "target"
    (t / ".git").mkdir(parents=True)          # satisfies _is_git_repo without needing the git binary
    (t / ".claude").mkdir()
    orig_settings = {
        "permissions": {"allow": ["Bash(ls:*)", "Read(//x/**)"]},
        "enabledMcpjsonServers": ["tao-knowledge"],
        "hooks": {"PreToolUse": [{"matcher": "*", "hooks": [{"type": "command", "command": "echo foreign"}]}]},
    }
    deploy._dump_json(deploy._settings_path(t), orig_settings)
    (t / ".gitignore").write_text("node_modules/\n*.log\n", encoding="utf-8")
    return t, orig_settings


def test_install_uninstall_roundtrip(tmp_path):
    t, orig_settings = _seed_target(tmp_path)

    r = deploy.install(str(t), mode="observe", integrity="enforce", declarative="off")
    assert r["ok"]
    s = deploy._load_json(deploy._settings_path(t))
    # our 6 events are wired...
    assert set(s["hooks"]) == {"PreToolUse", "PostToolUse", "PostToolUseFailure",
                               "UserPromptSubmit", "SessionStart", "PreCompact"}
    cmds = [h["command"] for g in s["hooks"]["PreToolUse"] for h in g["hooks"]]
    assert any(deploy._ours(c) for c in cmds)               # ours present
    assert "echo foreign" in cmds                            # ...ALONGSIDE the user's foreign hook
    # user keys untouched
    assert s["permissions"] == orig_settings["permissions"]
    assert s["enabledMcpjsonServers"] == orig_settings["enabledMcpjsonServers"]
    # activation config + gitignore + one-time backup
    cfg = deploy._load_json(deploy._config_path(t))
    assert cfg["integrity"]["mode"] == "enforce" and cfg["integrity"]["audit_chain"] is True
    assert cfg["somatic_gate"]["mode"] == "observe" and cfg["declarative"]["mode"] == "off"
    excl = (t / ".git" / "info" / "exclude").read_text()
    assert deploy._GI_BEGIN in excl                          # ignores in the LOCAL exclude (non-invasive)
    assert (t / ".gitignore").read_text() == "node_modules/\n*.log\n"   # tracked .gitignore is UNTOUCHED
    assert (deploy._state_dir(t) / "settings.local.json.bak").exists()   # backup lives in the gitignored state dir

    # --- the reversibility guarantee ---
    deploy.uninstall(str(t))
    after = deploy._load_json(deploy._settings_path(t))
    assert after == orig_settings                            # settings restored EXACTLY (foreign hook survives)
    assert not deploy._config_path(t).exists()               # activation file gone → dormant
    assert deploy._GI_BEGIN not in (t / ".git" / "info" / "exclude").read_text()   # exclude block gone
    assert (t / ".gitignore").read_text() == "node_modules/\n*.log\n"              # .gitignore never touched


def test_install_idempotent(tmp_path):
    t, _ = _seed_target(tmp_path)
    deploy.install(str(t))
    deploy.install(str(t))                                   # second install must not duplicate
    s = deploy._load_json(deploy._settings_path(t))
    our_pre = [h for g in s["hooks"]["PreToolUse"] for h in g["hooks"] if deploy._ours(h["command"])]
    assert len(our_pre) == 1                                 # exactly one of ours, not two
    assert (t / ".git" / "info" / "exclude").read_text().count(deploy._GI_BEGIN) == 1   # block appears once


def test_ignore_skips_when_already_present(tmp_path):
    """If the target already ignores the runtime state (e.g. a user committed the rules into .gitignore),
    install leaves .gitignore UNTOUCHED and writes no duplicate exclude block — never reformat the repo."""
    t, _ = _seed_target(tmp_path)
    (t / ".gitignore").write_text(".claude/exocortex/\n/exocortex_config.json\n", encoding="utf-8")
    deploy.install(str(t))
    assert deploy._GI_BEGIN not in (t / ".gitignore").read_text()          # not reformatted
    excl = t / ".git" / "info" / "exclude"
    assert (not excl.exists()) or deploy._GI_BEGIN not in excl.read_text()  # no duplicate written


def test_status_and_purge(tmp_path):
    t, _ = _seed_target(tmp_path)
    assert deploy.status(str(t))["installed"] is False
    deploy.install(str(t), declarative="live", vault=str(t), ingest="tracked")
    st = deploy.status(str(t))
    assert st["installed"] and st["our_hook_entries"] == 6
    assert st["modes"]["declarative"] == "live" and st["modes"]["ingest"] == "tracked"

    (deploy._state_dir(t) / "colony.json").write_text("{}", encoding="utf-8")   # simulate accrued data
    deploy.uninstall(str(t))                                 # default KEEPS data
    assert deploy._state_dir(t).exists()
    deploy.install(str(t)); deploy.uninstall(str(t), purge=True)               # --purge removes it
    assert not deploy._state_dir(t).exists()
