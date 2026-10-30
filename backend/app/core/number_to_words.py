"""
Amount-in-words conversion, English and Arabic — needed for the Rental
Receipt's "Amount in words" field. Nothing like this exists anywhere
else in the codebase (confirmed during the Phase 1 audit), so this is a
small, self-contained, dependency-free utility, not a new module.

Handles amounts up to low billions, split into whole units + minor
units (e.g. dinars + fils, dollars + cents) — the minor unit is always
expressed as a plain two/three-digit number over the currency's
subdivision, which is how amounts are conventionally written out on
Gulf-region financial documents (avoids getting the fractional word
grammar wrong across many possible currencies).
"""

_EN_ONES = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine",
            "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen",
            "Seventeen", "Eighteen", "Nineteen"]
_EN_TENS = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]
_EN_SCALES = ["", "Thousand", "Million", "Billion"]


def _en_below_thousand(n: int) -> str:
    if n == 0:
        return ""
    if n < 20:
        return _EN_ONES[n]
    if n < 100:
        return (_EN_TENS[n // 10] + (f"-{_EN_ONES[n % 10]}" if n % 10 else "")).strip("-")
    return _EN_ONES[n // 100] + " Hundred" + (f" {_en_below_thousand(n % 100)}" if n % 100 else "")


def _english_integer(n: int) -> str:
    if n == 0:
        return "Zero"
    parts = []
    scale_idx = 0
    while n > 0:
        chunk = n % 1000
        if chunk:
            chunk_words = _en_below_thousand(chunk)
            scale = _EN_SCALES[scale_idx]
            parts.append(f"{chunk_words} {scale}".strip())
        n //= 1000
        scale_idx += 1
    return " ".join(reversed(parts))


_AR_ONES = ["", "واحد", "اثنان", "ثلاثة", "أربعة", "خمسة", "ستة", "سبعة", "ثمانية", "تسعة",
            "عشرة", "أحد عشر", "اثنا عشر", "ثلاثة عشر", "أربعة عشر", "خمسة عشر", "ستة عشر",
            "سبعة عشر", "ثمانية عشر", "تسعة عشر"]
_AR_TENS = ["", "", "عشرون", "ثلاثون", "أربعون", "خمسون", "ستون", "سبعون", "ثمانون", "تسعون"]
_AR_HUNDREDS = ["", "مائة", "مئتان", "ثلاثمائة", "أربعمائة", "خمسمائة", "ستمائة", "سبعمائة", "ثمانمائة", "تسعمائة"]
_AR_SCALES = ["", "ألف", "مليون", "مليار"]


def _ar_below_thousand(n: int) -> str:
    if n == 0:
        return ""
    parts = []
    hundreds, rem = divmod(n, 100)
    if hundreds:
        parts.append(_AR_HUNDREDS[hundreds])
    if rem:
        if rem < 20:
            parts.append(_AR_ONES[rem])
        else:
            tens, ones = divmod(rem, 10)
            if ones:
                parts.append(f"{_AR_ONES[ones]} و{_AR_TENS[tens]}")
            else:
                parts.append(_AR_TENS[tens])
    return " و".join(parts) if len(parts) > 1 else (parts[0] if parts else "")


def _arabic_integer(n: int) -> str:
    if n == 0:
        return "صفر"
    chunks = []
    temp = n
    while temp > 0:
        chunks.append(temp % 1000)
        temp //= 1000
    parts = []
    for scale_idx in range(len(chunks) - 1, -1, -1):
        chunk = chunks[scale_idx]
        if not chunk:
            continue
        chunk_words = _ar_below_thousand(chunk)
        if scale_idx == 0:
            parts.append(chunk_words)
        elif chunk == 1:
            parts.append(_AR_SCALES[scale_idx])
        elif chunk == 2:
            parts.append(_AR_SCALES[scale_idx] + "ان")  # dual form, e.g. "ألفان"
        else:
            parts.append(f"{chunk_words} {_AR_SCALES[scale_idx]}")
    return " و".join(parts)


from decimal import Decimal
from typing import Optional


def amount_to_words(amount, currency_major: Optional[str] = None, currency_minor: Optional[str] = None, language: str = "en", minor_digits: int = 3) -> str:
    """
    amount: Decimal, int, or float, e.g. Decimal("350.500")
    language: "en" or "ar"
    minor_digits: how many digits the minor unit uses (3 for fils/KWD, 2 for cents/most others)
    currency_major/currency_minor: override the default currency name (Kuwaiti Dinars/Fils,
    or the Arabic equivalent) — pass your own for a different currency.
    """
    if currency_major is None:
        currency_major = "دينار كويتي" if language == "ar" else "Kuwaiti Dinars"
    if currency_minor is None:
        currency_minor = "فلس" if language == "ar" else "Fils"

    amount = Decimal(str(amount))
    whole = int(amount)
    minor_scale = 10 ** minor_digits
    minor = abs(int((amount - whole) * minor_scale))

    if language == "ar":
        whole_words = _arabic_integer(whole)
        if minor:
            return f"{whole_words} {currency_major} و{minor} {currency_minor} فقط لا غير"
        return f"{whole_words} {currency_major} فقط لا غير"

    whole_words = _english_integer(whole)
    if minor:
        return f"{whole_words} {currency_major} and {minor:0{minor_digits}d}/{minor_scale} {currency_minor} Only"
    return f"{whole_words} {currency_major} Only"
