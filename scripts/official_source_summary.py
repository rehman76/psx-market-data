#!/usr/bin/env python3
"""Produce credential-safe official-source health summary for GitHub Actions.

An overall successful research run is never evidence of official PSX verification.
"""
import argparse
import json
from pathlib import Path

ALLOWED_CODES={'NOT_CONFIGURED','EMPTY_RESPONSE','NON_CLOSING_DOCUMENT',
 'INVALID_CLOSING_ROWS','INVALID_CLOSING_ZIP','UNSUPPORTED_UNIX_COMPRESS_Z',
 'CLOSING_MEMBER_TOO_LARGE','DOWNLOAD_TOO_LARGE','SOURCE_URL_NOT_AUTHORIZED',
 'REDIRECT_OUTSIDE_AUTHORIZED_HOST','UNEXPECTED_DOWNLOAD_ERROR',
 'UNAUTHORIZED_OFFICIAL_DOWNLOAD_URL','EMPTY_OFFICIAL_DOWNLOAD_URL',
 'AMBIGUOUS_DATE_TEMPLATE','UNSUPPORTED_DATE_TEMPLATE'}

def safe_error(value):
    if not isinstance(value,str):
        return 'UNCLASSIFIED_FAILURE'
    if value in ALLOWED_CODES or (value.startswith('HTTP_STATUS_') and value[12:].isdigit() and len(value)<=16):
        return value
    if value.startswith('DOWNLOAD_TRANSPORT_') and value[19:].isalpha() and len(value)<=56:
        return value
    return 'UNCLASSIFIED_FAILURE'

def render(status):
    official=status.get('sources',{}).get('official_psx',{})
    attempted=bool(status.get('download_attempted'))
    downloaded=bool(status.get('download_succeeded'))
    health='FILE_FORMAT_ACCEPTED_NOT_AUTHENTICATED' if downloaded else 'DOWNLOAD_FAILED' if attempted else 'NOT_CONFIGURED'
    code=safe_error(status.get('download_error')) if attempted and not downloaded else 'NONE'
    session=status.get('download_session_date')
    session=session if isinstance(session,str) and len(session)==10 and session[4]=='-' and session[7]=='-' and session.replace('-','').isdigit() else 'NOT_RECORDED'
    lines=[
        '## Official PSX source health',
        '',
        '| Check | Result |',
        '| --- | --- |',
        f'| Direct closing-file acquisition | `{health}` |',
        f'| Requested completed session | `{session}` |',
        f'| Sanitized failure code | `{code}` |',
        '| Independent PSX DPS authentication | **NOT ESTABLISHED** |',
        f'| Stored research-data freshness | `{"FRESH" if status.get("data_freshness",{}).get("fresh") else "NOT_CONFIRMED_FRESH"}` |',
        '',
        'A green research workflow is **not** proof of verified official PSX prices.',
    ]
    if code=='HTTP_STATUS_404':
        lines.append('The configured date-resolved URL returned 404. Check the actual authorized Market Summary (Closing) ZIP link in the official PSX Downloads UI; do not guess endpoint paths.')
    elif code=='NON_CLOSING_DOCUMENT':
        lines.append('The endpoint returned non-closing content. Inspect its official source configuration and access permissions without exposing response bodies.')
    elif code!='NONE':
        lines.append('Official source acquisition is not verified. Review the fixed diagnostic code; do not promote any trade recommendations.')
    else:
        lines.append('Format acceptance alone does not establish origin, independent matching, licensing, or trade eligibility.')
    return '\n'.join(lines)+'\n'

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--status',default='publish/status.json')
    ap.add_argument('--out',required=True)
    args=ap.parse_args()
    status=json.loads(Path(args.status).read_text())
    Path(args.out).write_text(render(status))
    print('Official source health summary generated (sanitized).')
if __name__=='__main__':
    main()
