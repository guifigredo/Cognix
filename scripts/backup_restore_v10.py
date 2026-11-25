"""Backup e ensaio de restauração do banco + anexos (sem sobrescrever produção).

Exemplos:
  python scripts/backup_restore_v10.py backup --output ./backup-cognix.zip
  python scripts/backup_restore_v10.py restore --archive ./backup-cognix.zip --to ./restore-isolado
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import tempfile
import zipfile
from pathlib import Path


def digest(data):return hashlib.sha256(data).hexdigest()


def source_paths():
    root=Path(__file__).resolve().parents[1]
    db=Path(os.getenv('COGNIX_DB',str(root/'data'/'cognix.sqlite3'))).resolve()
    uploads=Path(os.getenv('COGNIX_UPLOAD_STORE',str(root/'data'/'question_uploads'))).resolve()
    return db,uploads


def snapshot(output):
    dbpath,store=source_paths()
    if not dbpath.is_file():raise ValueError('SGBD de origem inexistente.')
    output=Path(output).resolve()
    if output.exists():raise ValueError('Backup de destino já existe. Nada foi sobrescrito.')
    with tempfile.TemporaryDirectory() as staging:
        copy=Path(staging)/'database.sqlite3'
        with sqlite3.connect(dbpath) as source,sqlite3.connect(copy) as destination:
            source.backup(destination)
        with sqlite3.connect(copy) as db:
            names=[x[0] for x in db.execute('SELECT storage_key FROM question_attachments')]
            names+= [x[0] for x in db.execute('SELECT storage_key FROM question_batch_files')]
            names=list(dict.fromkeys(names))
        manifest={'version':'10.0','files':{},'attachment_count':len(names)}
        with zipfile.ZipFile(output,'x',compression=zipfile.ZIP_DEFLATED) as archive:
            data=copy.read_bytes()
            manifest['files']['database.sqlite3']=digest(data)
            archive.writestr('database.sqlite3',data)
            for key in names:
                if '/' in key or '..' in key or '\\' in key:
                    raise ValueError('Referência inválida de anexo encontrada.')
                path=store/key
                if not path.is_file():raise ValueError(f'Anexo ausente: {key}')
                content=path.read_bytes();name='attachments/'+key
                manifest['files'][name]=digest(content)
                archive.writestr(name,content)
            archive.writestr('manifest.json',json.dumps(manifest,indent=2))
    return manifest


def restore(archive,to):
    archive=Path(archive).resolve();dest=Path(to).resolve()
    if dest.exists():raise ValueError('Destino já existe. Restauração destrutiva não permitida.')
    with zipfile.ZipFile(archive) as bundle:
        manifest=json.loads(bundle.read('manifest.json'))
        files=manifest['files']
        if 'database.sqlite3' not in files:raise ValueError('Banco ausente no manifesto.')
        for name,hashval in files.items():
            if name not in bundle.namelist() or digest(bundle.read(name))!=hashval:
                raise ValueError('Arquivo ausente ou íntegro não confirmado: '+name)
            if name!='database.sqlite3' and (not name.startswith('attachments/') or
                len(Path(name).parts)!=2 or '..' in name):
                raise ValueError('Caminho inseguro no arquivo: '+name)
        dest.mkdir(parents=True)
        (dest/'attachments').mkdir()
        for name in files:
            path=dest/name
            path.write_bytes(bundle.read(name))
    db=sqlite3.connect(dest/'database.sqlite3')
    db.execute('PRAGMA foreign_keys=ON')
    errors=db.execute('PRAGMA foreign_key_check').fetchall()
    attachments=db.execute('''SELECT storage_key,sha256 FROM question_attachments
                  UNION SELECT storage_key,sha256 FROM question_batch_files''').fetchall()
    for key,sha in attachments:
        file=dest/'attachments'/key
        if not file.is_file() or digest(file.read_bytes())!=sha:
            raise ValueError('Anexo corrompido na restauração: '+key)
    counts={name:db.execute('SELECT COUNT(*) FROM '+name).fetchone()[0] for name in
            ('questions','question_collections','question_categories','question_records',
             'question_attachments','question_batch_files','exam_item_snapshots','school_memberships')}
    db.close()
    if errors:raise ValueError('Falha nas chaves estrangeiras após a restauração.')
    return {'verified':True,'counts':counts,'attachments':len(attachments)}


if __name__=='__main__':
    p=argparse.ArgumentParser()
    sub=p.add_subparsers(dest='mode',required=True)
    sub.add_parser('backup').add_argument('--output',required=True)
    r=sub.add_parser('restore');r.add_argument('--archive',required=True);r.add_argument('--to',required=True)
    a=p.parse_args()
    print(json.dumps(snapshot(a.output) if a.mode=='backup' else restore(a.archive,a.to),ensure_ascii=False,indent=2))
