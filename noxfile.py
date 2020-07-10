"""Entrypoint for nox."""

import tempfile

import nox


@nox.session(
    reuse_venv=True, python=["2.7", "3.4", "3.5", "3.6", "3.7", "3.8", "pypy", "pypy3"]
)
def tests(session):
    """Run all tests."""
    session.install(".")
    session.install("-r", "./requirements-test.txt")

    cmd = ["pytest"]
    if session.posargs:
        cmd.extend(session.posargs)
    session.run(*cmd)


@nox.session(reuse_venv=True, python="3.7")
def cop(session):
    """Run all pre-commit hooks."""
    session.install(".")
    session.install("-r", "requirements-dev.txt")

    session.run("pre-commit", "install")
    session.run("pre-commit", "run", "--show-diff-on-failure", "--all-files")


@nox.session(reuse_venv=True, python="3.7")
def bandit(session):
    """Run bandit."""
    session.install("bandit")
    session.run("bandit", "-r", "m2r.py", "-ll", "-c", "bandit.yaml")


@nox.session(reuse_venv=True, python="3.7")
def test_sphinx_old_build(session):
    """Build docs with sphinx."""
    with tempfile.TemporaryDirectory() as tmpdirname:
        session.install(".")
        session.install("sphinx==1.7.0")
        session.run("sphinx-build", "-W", "-E", "-n", "-b", "html", "docs", tmpdirname)


@nox.session(reuse_venv=True, python="3.7")
def test_sphinx_build(session):
    """Build docs with sphinx."""
    with tempfile.TemporaryDirectory() as tmpdirname:
        session.install(".")
        session.install("sphinx")
        session.run("sphinx-build", "-W", "-E", "-n", "-b", "html", "docs", tmpdirname)
