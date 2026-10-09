"""Admin provisioning and SQLite online backup."""
import argparse
import getpass
import os
import sqlite3
from pathlib import Path
from .db import initialize, transaction, connect
from .security import hash_password,new_id,now


def main():
    parser=argparse.ArgumentParser(description='Wichtelzauber verwalten')
    sub=parser.add_subparsers(dest='command',required=True)
    sub.add_parser('init-db',help='Datenbank initialisieren')
    sub.add_parser('init-admin',help='Admin sicher über Terminal anlegen')
    back=sub.add_parser('backup',help='SQLite-Datenbank konsistent sichern')
    back.add_argument('filename')
    args=parser.parse_args()
    initialize()
    if args.command=='init-db':
        print('Datenbank eingerichtet.')
    elif args.command=='init-admin':
        username=input('Admin-Benutzername: ').strip()
        if not (3<=len(username)<=80): raise SystemExit('Benutzername muss 3–80 Zeichen haben.')
        password=getpass.getpass('Admin-Passwort (mind. 12 Zeichen): ')
        again=getpass.getpass('Passwort wiederholen: ')
        if len(password)<12 or password != again: raise SystemExit('Passwort zu kurz oder unterschiedlich.')
        with transaction() as conn:
            if conn.execute('SELECT 1 FROM admins WHERE username=? COLLATE NOCASE',(username,)).fetchone():
                raise SystemExit('Benutzername existiert bereits.')
            conn.execute('INSERT INTO admins (id,username,password_hash,created_at) VALUES (?,?,?,?)',
                         (new_id(),username,hash_password(password),now()))
        print('Admin erfolgreich angelegt.')
    elif args.command=='backup':
        destination=Path(args.filename).resolve()
        destination.parent.mkdir(parents=True,exist_ok=True)
        with connect() as src, sqlite3.connect(destination) as dest:
            src.backup(dest)
        print('Sicherung erstellt:',destination)


if __name__=='__main__': main()
