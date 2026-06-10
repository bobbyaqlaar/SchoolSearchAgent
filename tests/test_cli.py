"""Tests for dubai.cli sync entrypoint."""

from __future__ import annotations


def test_parse_args_dry_run_flag():
    from dubai.cli import _parse_args

    assert _parse_args(["--dry-run"]).dry_run is True
    assert _parse_args([]).dry_run is False


def test_main_dry_run_skips_neo4j(mocker, capsys):
    import dubai.cli as cli_mod

    mocker.patch.object(cli_mod, "Neo4jClient")
    assert cli_mod.main(["--dry-run"]) == 0
    cli_mod.Neo4jClient.assert_not_called()
    assert "DRY RUN OK" in capsys.readouterr().out


def test_main_success_prints_summary(mocker, capsys):
    import dubai.cli as cli_mod

    fake_client = mocker.Mock()
    mocker.patch.object(cli_mod, "Neo4jClient", return_value=fake_client)
    fake_app = mocker.Mock()
    fake_app.invoke.return_value = {
        "audit_logs": {
            "initial_pending_count": 2,
            "created": 1,
            "updated": 1,
            "validation_failures": 0,
            "extraction_failures": 0,
            "failures_recorded": 0,
        }
    }
    mocker.patch.object(cli_mod, "compile_sync_workflow", return_value=fake_app)

    assert cli_mod.main([]) == 0
    out = capsys.readouterr().out
    assert "New schools created   : 1" in out
    fake_client.apply_constraints.assert_called_once()
    fake_client.close.assert_called_once()


def test_main_pipeline_failure(mocker):
    import dubai.cli as cli_mod

    fake_client = mocker.Mock()
    mocker.patch.object(cli_mod, "Neo4jClient", return_value=fake_client)
    fake_app = mocker.Mock()
    fake_app.invoke.side_effect = RuntimeError("boom")
    mocker.patch.object(cli_mod, "compile_sync_workflow", return_value=fake_app)

    assert cli_mod.main([]) == 1
    fake_client.close.assert_called_once()


def test_main_closes_client_on_exception(mocker):
    import dubai.cli as cli_mod

    fake_client = mocker.Mock()
    mocker.patch.object(cli_mod, "Neo4jClient", return_value=fake_client)
    mocker.patch.object(cli_mod, "compile_sync_workflow", side_effect=RuntimeError("init fail"))

    assert cli_mod.main([]) == 1
    fake_client.close.assert_called_once()
