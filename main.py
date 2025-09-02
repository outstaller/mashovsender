#!/usr/bin/env python3
"""
Mashov REST-style sender script.
Reads a CSV with Hebrew headers, looks up each student by ת.ז. (or name) using Mashov web API endpoints,
and sends them a message with username/password via the built-in messaging endpoints.

CSV expected columns:
  ת.ז, שם פרטי, שם משפחה, שם משתמש, שם משתמש עם דומיין, סיסמא

Usage:
  pip install requests pandas python-dotenv
  # add .env with MASHOV_USER, MASHOV_PASS, MASHOV_YEAR, MASHOV_SEMEL
  python mashov_api_sender.py --csv /path/to/userlist.csv --dry-run
  python mashov_api_sender.py --csv /path/to/userlist.csv --limit 5
"""
import os
import sys
import argparse
from dotenv import load_dotenv
import pandas as pd
from mashov_api import MashovClient, read_students, compose, DEFAULT_SUBJECT, DEFAULT_TEMPLATE


def main():
    load_dotenv()
    ap = argparse.ArgumentParser(description="Send Mashov messages")
    ap.add_argument("--csv", help="Input CSV path (UTF-8).", default="userlist.csv")
    ap.add_argument("--subject", default=DEFAULT_SUBJECT)
    ap.add_argument("--template", default=DEFAULT_TEMPLATE)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--dry-run", action="store_true", help="Don't POST send; only resolve recipients and print.")
    ap.add_argument("--export", metavar="OUT_CSV", help="Write recipient+subject+body CSV (no API calls).")
    args = ap.parse_args()

    user = os.getenv("MASHOV_USER")
    pwd = os.getenv("MASHOV_PASS")
    year = os.getenv("MASHOV_YEAR")
    semel = os.getenv("MASHOV_SEMEL")
    if not all([user, pwd, year, semel]):
        print("Missing one of MASHOV_USER, MASHOV_PASS, MASHOV_YEAR, MASHOV_SEMEL in .env", file=sys.stderr)
        sys.exit(2)
    # Ensure all are str, not None
    user = str(user)
    pwd = str(pwd)
    year = str(year)
    semel = str(semel)

    # All variables are guaranteed to be str here
    rows = read_students(args.csv)
    if args.limit: 
        rows = rows[: args.limit]

    if args.export:
        out = [{"student_display_name": s.display_name, "student_id": s.id,
                "subject": compose(s, args.subject, args.template)[0],
                "body": compose(s, args.subject, args.template)[1]} for s in rows]
        pd.DataFrame(out).to_csv(args.export, index=False, encoding="utf-8")
        print(f"Wrote {len(out)} rows to {args.export}")
        return

    client = MashovClient(user, pwd, year, semel)
        
    try: 
        sender=client.login()
        print(f"Logged in as: {sender.get("accessToken",{}).get("displayName") if isinstance(sender, dict) else None}")
    except Exception: 
        print("Login failed. Cannot continue")
        exit(1)

    successes, failures = 0, 0
    for stu in rows:
        subject, body = compose(stu, args.subject, args.template)
        t = None
        try: 
            t = client.locate_by_id(stu.id) if stu.id else None
        except Exception: 
            pass

        if not t:
            print(f"[SKIP] No match for {stu.display_name} ({stu.id})")
            failures += 1
            continue

        #classCode=t.get('classCode')
        #classNum=t.get('classNum')
        #familyName=t.get('familyName')
        #privateName=t.get('privateName')
        #displayName=f"כיתה/{classCode}/{classNum}/{familyName} {privateName}"
        #client.send_message("בדיקת חיבור", f"בדיקת חיבור למערכת בשם {displayName}", [t.get('studentGuid')])

        recipient_id = t.get("studentGuid")
        if not recipient_id:
            print(f"[SKIP] Could not extract studentGuid for {stu.display_name}")
            failures += 1
            continue

        if args.dry_run:
            print(f"[DRY] Would send to {stu.display_name} ({recipient_id}) subject='{subject}'")
            continue

        try:
            client.send_message(subject, body, [recipient_id])
            print(f"[OK] Sent to {stu.display_name} ({recipient_id})")
            successes += 1
        except Exception as e:
            print(f"[FAIL] {stu.display_name}: {e}")
            failures += 1

    print(f"Done. success={successes}, failed={failures}")

if __name__ == "__main__":
    main()
