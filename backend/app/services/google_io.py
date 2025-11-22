from __future__ import annotations

from typing import Optional


def build_spreadsheet_url(sheet_id: str) -> str:
    return f"https://docs.google.com/spreadsheets/d/{sheet_id}/edit"


def get_default_input_url(sheet_id: str) -> str:
    return build_spreadsheet_url(sheet_id)


def get_default_output_url(sheet_id: str) -> str:
    return build_spreadsheet_url(sheet_id)


def summarize_sheet_target(sheet_id: str) -> dict:
    return {
        "spreadsheetId": sheet_id,
        "input_url": get_default_input_url(sheet_id),
        "output_url": get_default_output_url(sheet_id),
    }



