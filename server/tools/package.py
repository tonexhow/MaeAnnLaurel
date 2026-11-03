"""Create a portable source ZIP with no database, secrets, build output or caches."""
from __future__ import annotations
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEST = ROOT.parent / (ROOT.name + '-Stateless-Vercel-Ready.zip')
ROOT_FILES = ('.gitignore', '.env', '.env.example', 'start.bat', 'zip.bat', 'README.md')
ROOT_FOLDERS = ('client', 'server')
IGNORED_DIRS = {'.git', '.venv', 'venv', '__pycache__', '.pytest_cache', '.vercel', 'node_modules', 'dist', '.mypy_cache'}
IGNORED_NAMES = {'config.generated.js', 'fonts.local.css'}
SKIP_EXTENSIONS = {'.pyc', '.pyo', '.log', '.db', '.sqlite', '.sqlite3', '.ttf', '.otf', '.woff', '.zip', '.tmp', '.partial', '.pem', '.p12', '.pfx'}
REQUIRED_FONTS = (
    'client/assets/fonts/Inter/inter-latin-variable.woff2',
    'client/assets/fonts/Inter/inter-latin-italic.woff2',
    'client/assets/fonts/Manrope/manrope-latin-variable.woff2',
)


def main():
    if sys.version_info[:2] != (3, 13):
        raise SystemExit('Use Python 3.13 to run zip.bat.')
    missing = [p for p in ROOT_FILES + ROOT_FOLDERS if not (ROOT / p).exists()]
    if missing:
        raise SystemExit('Required project root entries are missing: ' + ', '.join(missing))
    contents = {}
    for dirname in ROOT_FOLDERS:
        for path in sorted((ROOT / dirname).rglob('*')):
            if not path.is_file() or path.is_symlink():
                continue
            rel = path.relative_to(ROOT)
            if IGNORED_DIRS.intersection(rel.parts) or any(part.startswith('.venv-') for part in rel.parts):
                continue
            if path.name in IGNORED_NAMES or path.suffix.lower() in SKIP_EXTENSIONS:
                continue
            if path.name == '.env' or (path.name.startswith('.env.') and path.name != '.env.example'):
                continue
            contents[rel.as_posix()] = path.read_bytes()
        template = ROOT / dirname / '.env.example'
        if template.is_file():
            contents[f'{dirname}/.env'] = template.read_bytes()
    for filename in ROOT_FILES:
        contents[filename] = (ROOT / ('.env.example' if filename == '.env' else filename)).read_bytes()
    if not (ROOT / 'client/index.html').is_file() or not (ROOT / 'server/app.py').is_file():
        raise SystemExit('Source files are incomplete.')
    for font in REQUIRED_FONTS:
        if font not in contents or not contents[font].startswith(b'wOF2'):
            raise SystemExit('Missing local WOFF2 font: ' + font)
    if any('database/' in path or 'database.db' in path for path in contents):
        raise SystemExit('Unexpected database file in package.')
    with zipfile.ZipFile(DEST, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=8) as archive:
        for folder in (*ROOT_FOLDERS, 'client/assets/career'):
            archive.writestr(f'{ROOT.name}/{folder}/', b'')
        for path, content in sorted(contents.items()):
            archive.writestr(f'{ROOT.name}/{path}', content)
    with zipfile.ZipFile(DEST) as archive:
        bad = archive.testzip()
        if bad:
            raise SystemExit('Archive integrity error: ' + bad)
        root_names = {name.split('/')[1] for name in archive.namelist() if len(name.split('/')) > 1 and name.split('/')[1]}
        expected = set(ROOT_FILES) | set(ROOT_FOLDERS)
        if root_names != expected:
            raise SystemExit(f'Unexpected root entries: {root_names ^ expected}')
    print('Created:', DEST)
    print('Included:', len(contents), 'files; no database, passwords, local caches or test artifacts.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
