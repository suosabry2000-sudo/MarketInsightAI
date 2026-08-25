from pathlib import Path
import subprocess, sys

ROOT=Path(__file__).resolve().parents[3]

def test_secret_scanner_flags_forbidden_value(tmp_path):
    scanner=ROOT/'scripts'/'check_no_secrets.py'
    target=tmp_path/'payload.txt'; target.write_text('prefix ACTUAL_SECRET_VALUE suffix')
    p=subprocess.run([sys.executable,str(scanner),str(target)],env={'FORBIDDEN_SECRET_VALUES':'ACTUAL_SECRET_VALUE'},capture_output=True,text=True)
    assert p.returncode != 0
    assert 'forbidden secret' in (p.stdout+p.stderr).lower()

def test_release_verifier_has_required_gates():
    text=(ROOT/'scripts'/'verify_release.sh').read_text()
    for needle in ('pytest','testDebugUnitTest','assembleDebug','assembleRelease','apksigner verify','check_no_secrets.py','SHA256SUMS.txt'):
        assert needle in text


def test_backend_dockerfile_honors_platform_port():
    text=(ROOT/'backend'/'Dockerfile').read_text()
    assert '${PORT:-8000}' in text
