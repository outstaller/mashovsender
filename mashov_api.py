
import re
import os, sys, json, unicodedata
from dataclasses import dataclass
from typing import Optional, List, Dict, Any

import requests
import pandas as pd
from dotenv import load_dotenv

BASE = "https://web.mashov.info"
API  = BASE + "/api"

LOGIN_ENDPOINT = API + "/login"
SEARCH_STUDENTS_ENDPOINT = API + "/students/details"
SEND_MESSAGE_ENDPOINT = API + "/mail/messages"
RECIPIENTS_ENDPOINT = API + "/mail/recipients"

CSRF_HEADER_NAME = "X-Csrf-Token"
CSRF_COOKIE_NAME = "csrf-token"

HE_COLS = {
    "id": "ת.ז",
    "first": "שם פרטי",
    "last": "שם משפחה",
    "username": "שם משתמש",
    "username_domain": "שם משתמש עם דומיין",
    "password": "סיסמא",
}

DEFAULT_SUBJECT = "פרטי התחברות למערכת. נא לא למחוק ולא להעביר הלאה!"
DEFAULT_TEMPLATE = (
'<div style="font-weight:bold">שלום {first} {last},&nbsp;</div>'
'<div>&nbsp;</div>'
'<div>להלן פרטי ההתחברות שלך:</div>'
'<div>שם משתמש: <p style="direction:ltr;text-align:right;font-weight:bold">{username_with_domain}</p></div>'
'<div>סיסמה: <p style="direction:ltr;text-align:right;font-weight:bold">{password}</p></div>'
'<div>&nbsp;</div>'
'<div>אנא שמור/י על הפרטים בסוד ואל תעביר/י אותם לאחרים.</div>'
'<div>ניתן לבצע איפוס סיסמא דרך הקישור <a href="http://bit.ly/forgotPass">http://bit.ly/forgotPass</a>&nbsp;.</div>'
'<div>&nbsp;</div>'
'<div>אם יש לך שאלות או בעיות, פנה/י למורה או למזכירות בית הספר.&nbsp;</div>'
'<div>בהצלחה,</div>'
'<div>צוות בית הספר</div>'
)

@dataclass
class StudentRow:
    id: str
    first: str
    last: str
    username: str
    username_with_domain: str
    password: str

    @property
    def display_name(self) -> str:
        return f"{self.first} {self.last}".strip()

def normalize_id(raw) -> str:
    if pd.isna(raw): 
        return ""
    s = str(raw).strip()
    if s.endswith(".0"): 
        s = s[:-2]
    s = "".join(ch for ch in s if ch.isdigit())
    return s.zfill(9) if s else ""

def norm(s: Optional[str]) -> str:
    if s is None or (isinstance(s, float) and pd.isna(s)): 
        return ""
    return unicodedata.normalize("NFC", str(s).strip())

def read_students(csv_path: str) -> List[StudentRow]:
    df = pd.read_csv(csv_path, dtype=str)
    rows: List[StudentRow] = []
    for _, r in df.iterrows():
        rows.append(StudentRow(
            id=normalize_id(r.get(HE_COLS["id"])),
            first=norm(r.get(HE_COLS["first"])),
            last=norm(r.get(HE_COLS["last"])),
            username=norm(r.get(HE_COLS["username"])).removesuffix(".0"),
            username_with_domain=norm(r.get(HE_COLS["username_domain"])),
            password=norm(r.get(HE_COLS["password"])),
        ))
    return rows

class MashovClient:
    def __init__(self, user: str, pwd: str, year: str, semel: str, timeout: int = 25):
        self.s = requests.Session()
        self.user, self.pwd, self.year, self.semel = user, pwd, str(year), str(semel)
        self.timeout, self.csrf = timeout, None
        self.s.headers.update({
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json;charset=UTF-8",
            "Origin": BASE,
            "Referer": BASE + "/teachers/login",
            "User-Agent": "MashovAPI-Python/1.0",
        })

    def login(self) -> Dict[str, Any]:
        payload = {"username": self.user, "password": self.pwd, "year": self.year, "semel": self.semel}
        r = self.s.post(LOGIN_ENDPOINT, data=json.dumps(payload), timeout=self.timeout)
        r.raise_for_status()
        data = r.json() if r.content else {}
        # Find CSRF token in cookies (case-insensitive)
        for cookie in self.s.cookies:
            if cookie.name.lower() == CSRF_COOKIE_NAME.lower():
                self.csrf = cookie.value
                self.s.headers[CSRF_HEADER_NAME] = self.csrf
                break
        self.logged_in_user = data #.get("accessToken").get("displayName") if isinstance(data, dict) else None
        return data
    
    def locate_by_id(self, student_id: str) -> Dict[str, Any]:
        r = self.s.get(f"{SEARCH_STUDENTS_ENDPOINT}/{student_id}", timeout=self.timeout)
        r.raise_for_status()
        data = r.json()
        # return student details
        if isinstance(data, list) and data:
            return data[0].get("student", None)
        return None

    def recipients(self) -> List[Dict[str, Any]]:
        r = self.s.get(RECIPIENTS_ENDPOINT, timeout=self.timeout)
        r.raise_for_status()
        data = r.json() if r.content else []
        return data if isinstance(data, list) else []
    
    def send_message(self, subject: str, body: str, recipient_student_ids: List[str], sendViaEmail=False) -> Dict[str, Any]:
        payload = {
            "subject": subject,
            "body": body,
            "recipients": [{"targetType": "User", "valueType": "User", "value": sid} for sid in recipient_student_ids],
            "send": True,
            "sendViaEmail": str(sendViaEmail).lower(),
            # "sentViaEmail": "true",
            "preventReply": "true",
        }
        r = self.s.post(SEND_MESSAGE_ENDPOINT, data=json.dumps(payload), timeout=self.timeout)
        r.raise_for_status()
        return r.json() if r.content else {"ok": True}

def compose(stu: StudentRow, subject: Optional[str], template: Optional[str]) -> tuple[str, str]:
    subject = subject or DEFAULT_SUBJECT
    body = (template or DEFAULT_TEMPLATE).format(
        first=stu.first,
        last=stu.last,
        username=stu.username,
        username_with_domain=f"({stu.username_with_domain})" if stu.username_with_domain else "",
        password=stu.password,
    )
    return subject, body
