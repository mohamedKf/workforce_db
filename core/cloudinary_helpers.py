"""
Cloudinary upload/delete/signed-URL helpers for WorkForce.

All file uploads are stored as `authenticated` type with signed URLs.
Without the API secret, no one can generate a valid URL → uploads are
genuinely private even if someone knows the public_id.

Notes on signed URL semantics:
- The URL hash protects against URL forgery — only someone with the API
  secret can generate working URLs.
- Once generated, a signed URL DOES NOT auto-expire on the free tier.
  Cloudinary's time-limited URLs (auth tokens) are a paid feature.
- For our use case (internal app, photos of receipts/contracts) this is
  sufficient: URLs only ever live in the Django DB and are sent over
  HTTPS to authenticated users.

Usage:

    from core.cloudinary_helpers import upload_file, delete_file, signed_url

    # Upload from a Django UploadedFile
    public_id, _ = upload_file(
        django_file,
        folder='workforce/invoices/2026/05',
        prefix='inv',
    )

    # Generate signed URL for the app to display
    url = signed_url(public_id)

    # Delete asset (e.g. when its parent record is deleted)
    delete_file(public_id)
"""

from __future__ import annotations

import logging
import time
from typing import Tuple

import cloudinary
import cloudinary.uploader
import cloudinary.utils

log = logging.getLogger(__name__)


# Files larger than this (MB) are rejected to avoid eating the Cloudinary quota.
MAX_FILE_SIZE_MB = 10


# ─── Upload ───────────────────────────────────────────────────────────────

def upload_file(
    django_file,
    folder: str,
    prefix: str = "",
    resource_type: str = "auto",
) -> Tuple[str, dict]:
    """
    Upload a Django UploadedFile to Cloudinary as a private (authenticated)
    asset.

    Args:
        django_file: A Django UploadedFile (or any file-like with .read()).
        folder: Cloudinary folder, e.g. 'workforce/invoices/2026/05'.
        prefix: Optional public_id prefix (e.g. 'inv', 'site').
        resource_type: 'image', 'video', 'raw', or 'auto'. Use 'auto'
                       when the same endpoint can receive images or PDFs.

    Returns:
        (public_id, full_response_dict) — store public_id in DB.

    Raises:
        ValueError if the file is too large or upload fails.
    """
    if not django_file:
        raise ValueError("No file provided")

    # Size check
    size_bytes = getattr(django_file, "size", None)
    if size_bytes is not None:
        size_mb = size_bytes / (1024 * 1024)
        if size_mb > MAX_FILE_SIZE_MB:
            raise ValueError(
                f"File too large: {size_mb:.1f}MB (max {MAX_FILE_SIZE_MB}MB)"
            )

    # Build a unique public_id with timestamp so re-uploads of same name
    # don't collide.
    timestamp = int(time.time())
    public_id_base = f"{prefix}_{timestamp}" if prefix else str(timestamp)

    try:
        result = cloudinary.uploader.upload(
            django_file,
            folder          = folder,
            public_id       = public_id_base,
            resource_type   = resource_type,
            type            = "authenticated",   # Private — signed URL required
            use_filename    = False,
            unique_filename = True,
            overwrite       = False,
        )
    except Exception as e:
        log.exception(f"Cloudinary upload failed (folder={folder}, prefix={prefix})")
        raise ValueError(f"Upload failed: {e}")

    public_id = result.get("public_id", "")
    log.info(f"Cloudinary upload OK: {public_id} ({result.get('bytes', 0)} bytes)")
    return public_id, result


# ─── Delete ───────────────────────────────────────────────────────────────

def delete_file(public_id: str, resource_type: str = "image") -> bool:
    """
    Delete an asset from Cloudinary by public_id.

    Tries the given resource_type first; falls back to other types if it
    wasn't found. Returns True on success, False otherwise (logged).
    """
    if not public_id:
        return False

    types_to_try = [resource_type] + [t for t in ("image", "raw", "video") if t != resource_type]
    for rtype in types_to_try:
        try:
            result = cloudinary.uploader.destroy(
                public_id,
                type           = "authenticated",
                resource_type  = rtype,
            )
            if result.get("result") == "ok":
                log.info(f"Cloudinary delete OK: {public_id} (resource_type={rtype})")
                return True
        except Exception:
            log.exception(f"Cloudinary delete error: {public_id} ({rtype})")
            continue

    log.warning(f"Cloudinary delete: {public_id} not found in any resource_type")
    return False


# ─── Signed URL generation ────────────────────────────────────────────────

def signed_url(public_id: str, resource_type: str = "image") -> str:
    """
    Generate a signed delivery URL for a private asset.

    The URL contains an HMAC signature derived from the API secret. Anyone
    can use the URL to fetch the asset, but only someone with the secret
    can generate a valid URL in the first place.

    Args:
        public_id: The Cloudinary public_id stored in the DB.
        resource_type: 'image' for photos, 'raw' for PDFs/docs.

    Returns:
        Full signed URL. Empty string if public_id is empty or signing fails.
    """
    if not public_id:
        return ""
    try:
        url, _options = cloudinary.utils.cloudinary_url(
            public_id,
            type           = "authenticated",
            resource_type  = resource_type,
            sign_url       = True,
            secure         = True,
        )
        return url or ""
    except Exception:
        log.exception(f"Failed to generate signed URL for {public_id}")
        return ""


def signed_url_for(public_id: str, file_extension: str = "") -> str:
    """
    Convenience wrapper that picks resource_type from a file extension.
    """
    ext = (file_extension or "").lower().lstrip(".")
    if ext in ("pdf", "doc", "docx", "xls", "xlsx", "txt"):
        return signed_url(public_id, resource_type="raw")
    return signed_url(public_id, resource_type="image")