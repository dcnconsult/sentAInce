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


# ---- artifact 4: the agent bootstrap contract ----
def test_bootstrap_contract_claude_appends_and_uninstall_restores(tmp_path):
    """AGENTS.md: user content is never clobbered; our block is marker-delimited, idempotent on
    re-install, and uninstall removes exactly the block."""
    t, _ = _seed_target(tmp_path)
    user_text = "# My project\nHouse rules the user wrote.\n"
    (t / "AGENTS.md").write_text(user_text, encoding="utf-8")

    r = deploy.install(str(t), mode="somatic")
    assert any(p.endswith("AGENTS.md") for p in r["bootstrap"])
    text = (t / "AGENTS.md").read_text(encoding="utf-8")
    assert text.startswith("# My project")                     # user content first, untouched
    assert deploy._BS_BEGIN in text and deploy._BS_END in text
    assert 'recall_for_prompt(prompt, cls="<class>")' in text  # the deterministic bootstrap path
    assert "earned suggestion, never authority" in text        # the phrasing gap, closed
    assert "refuse" in text                                    # somatic mode disclosure
    assert text.count(deploy._BS_BEGIN) == 1

    deploy.install(str(t), mode="observe")                     # re-install with a different mode
    text2 = (t / "AGENTS.md").read_text(encoding="utf-8")
    assert text2.count(deploy._BS_BEGIN) == 1                  # replaced in place, not duplicated
    assert "audit-only" in text2                               # mode disclosure updated

    res = deploy.uninstall(str(t))
    assert res["bootstrap_removed"]
    remaining = (t / "AGENTS.md").read_text(encoding="utf-8")
    assert deploy._BS_BEGIN not in remaining
    assert remaining.startswith("# My project")                # user content survives


def test_bootstrap_contract_owns_file_when_user_has_none(tmp_path):
    """No pre-existing AGENTS.md: we create it; uninstall removes it entirely (no trace)."""
    t, _ = _seed_target(tmp_path)
    deploy.install(str(t), mode="observe")
    assert (t / "AGENTS.md").exists()
    deploy.uninstall(str(t))
    assert not (t / "AGENTS.md").exists()


def test_bootstrap_contract_cursor_writes_mdc_rule(tmp_path):
    t, _ = _seed_target(tmp_path)
    deploy.install(str(t), mode="somatic", provider="cursor")
    mdc = t / ".cursor" / "rules" / "exocortex-bootstrap.mdc"
    assert mdc.exists()
    text = mdc.read_text(encoding="utf-8")
    assert text.startswith("---\n") and "alwaysApply: true" in text
    assert "memory_status" in text and "never authority" in text
    deploy.uninstall(str(t))
    assert not mdc.exists()


# ---- artifact 6: the recall skill (.claude/skills/sentaince-recall/SKILL.md) ----
def test_skill_installed_and_uninstall_prunes(tmp_path):
    t, _ = _seed_target(tmp_path)
    r = deploy.install(str(t))
    p = deploy._skill_path(t)
    assert r["skill"] == str(p) and p.exists()
    text = p.read_text(encoding="utf-8")
    assert text.startswith("---\nname: sentaince-recall")     # skill frontmatter intact
    assert deploy._SKILL_MARK in text                          # ownership marker present
    assert "earned suggestion, never authority" in text        # the law rides in the skill
    assert deploy.status(str(t))["skill_present"] is True

    deploy.uninstall(str(t))
    assert not p.exists()
    assert not (t / ".claude" / "skills").exists()             # empty skill dirs pruned
    assert (t / ".claude").exists()                            # shared parent untouched
    assert deploy.status(str(t))["skill_present"] is False


def test_skill_never_clobbers_foreign_and_uninstall_leaves_it(tmp_path):
    t, _ = _seed_target(tmp_path)
    p = deploy._skill_path(t)
    p.parent.mkdir(parents=True)
    foreign = "---\nname: sentaince-recall\n---\nthe user's own skill\n"
    p.write_text(foreign, encoding="utf-8")

    r = deploy.install(str(t))
    assert r["skill"] is None                                  # not installed
    assert any("foreign skill" in w for w in r["warnings"])    # ...and said so
    assert p.read_text(encoding="utf-8") == foreign            # byte-untouched
    assert deploy.status(str(t))["skill_present"] is False     # ours is absent (marker check)

    deploy.uninstall(str(t))
    assert p.read_text(encoding="utf-8") == foreign            # uninstall leaves foreign file alone


def test_skill_reinstall_idempotent_and_cursor_only_skips(tmp_path):
    t, _ = _seed_target(tmp_path)
    deploy.install(str(t))
    first = deploy._skill_path(t).read_text(encoding="utf-8")
    deploy.install(str(t))                                     # re-deploy refreshes our own file in place
    assert deploy._skill_path(t).read_text(encoding="utf-8") == first

    t2 = tmp_path / "cursor-only"
    (t2 / ".git").mkdir(parents=True)
    r2 = deploy.install(str(t2), provider="cursor")            # skills are a Claude Code surface
    assert r2["skill"] is None and not deploy._skill_path(t2).exists()


# --------------------------- integrity default: the bug that bricked every pip user ---------------------------
def test_install_does_not_enable_integrity_enforce(tmp_path):
    """REGRESSION (confirmed live 2026-07-16, clean venv): `deploy install` defaulted to
    `integrity=enforce` and bricked EVERY pip user's SessionStart.

    The chain: the wheel ships `exocortex/integrity_baseline.json` but NOT `vendor/` (pyproject
    `packages = [sentaince, exocortex, cerebral]`), while 3 of 4 LOCKED_GLOBS are `vendor/kernel/**` and
    56 of the baseline's 66 entries live there. In a wheel `integrity._REPO_ROOT` resolves to
    site-packages, so those 56 are `missing` -> `verify_kernel()` ok=False -> hook.py's apoptosis
    `sys.exit(1)` on EVERY SessionStart. The fail-open cannot catch it (`except SystemExit: raise`), so
    state was never seeded, `resplice` never set, and MEMORY NEVER SPLICED. Measured before/after in a
    clean venv: SessionStart exit 1 -> 0; `state_<sid>.json` absent -> present.

    `off` is not a weakening: it is the Genome's OWN default and its stated reason -- "Ships DORMANT so a
    stale baseline never bricks dev" (genome.py). Deploy was overriding exactly the protection the genome
    wrote that comment to provide, and it made three shipped promises false: "watch-only ... changes
    nothing" (QUICKSTART), "the organism never wedges your session" (QUICKSTART -- the rule that outranks
    every feature), and "dormant-by-default guardrails" (oasf-record.json).

    `enforce` remains available for a full checkout that actually carries vendor/kernel -- opt in there.
    """
    import inspect
    sig = inspect.signature(deploy.install)
    assert sig.parameters["integrity"].default == "off", (
        "deploy.install must not default to a mode that fails closed on a distribution whose baseline "
        "cannot be satisfied -- see this test's docstring")

    t, _ = _seed_target(tmp_path)
    deploy.install(str(t))
    cfg = deploy._load_json(t / "exocortex_config.json")
    assert cfg["integrity"]["mode"] == "off"
    assert cfg["integrity"]["audit_chain"] is True     # cheap + fail-open: stays on


def test_integrity_enforce_is_still_opt_in_and_honoured(tmp_path):
    """The rescue must not remove the capability -- only the accidental default."""
    t, _ = _seed_target(tmp_path)
    deploy.install(str(t), integrity="enforce")
    cfg = deploy._load_json(t / "exocortex_config.json")
    assert cfg["integrity"]["mode"] == "enforce"


def test_the_baseline_still_cannot_be_satisfied_without_vendor(tmp_path):
    """Pins the LANDMINE itself, so anyone tempted to flip the default back sees why it fails.

    If this ever starts passing with ok=True, either vendor/ began shipping or the baseline became
    distribution-aware -- and the default above can be revisited deliberately, on evidence.
    """
    from exocortex import integrity
    empty = tmp_path / "norepo"
    (empty / "sentaince" / "organism").mkdir(parents=True)
    r = integrity.verify_kernel(root=empty)
    assert r["ok"] is False
    assert any(p.startswith("vendor/kernel/") for p in r["missing"]), (
        "expected the vendor/kernel baseline entries to be unsatisfiable without a full checkout")
