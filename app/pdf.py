"""
Conversor docx → pdf usando LibreOffice headless.

Falla con ConversionError si LibreOffice no está disponible o si la conversión
no produce un PDF de salida. La excepción se propaga al endpoint que llama.
"""
import os
import shutil
import subprocess
import tempfile


SOFFICE_CANDIDATES = [
    "soffice",
    "libreoffice",
    r"C:\Program Files\LibreOffice\program\soffice.exe",
    r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
    "/usr/bin/soffice",
    "/usr/bin/libreoffice",
]


class ConversionError(RuntimeError):
    pass


def _resolver_soffice() -> str:
    """Devuelve la ruta a soffice o lanza ConversionError."""
    for cand in SOFFICE_CANDIDATES:
        path = shutil.which(cand) if not os.path.isabs(cand) else (cand if os.path.exists(cand) else None)
        if path:
            return path
    raise ConversionError(
        "LibreOffice (soffice) no está instalado o no se encontró en PATH. "
        "Instala libreoffice-writer en el contenedor."
    )


def docx_a_pdf(docx_path: str, out_dir: str, timeout: int = 30) -> str:
    """
    Convierte `docx_path` a PDF en `out_dir`. Devuelve la ruta al PDF resultante.

    LibreOffice escribe un archivo con el mismo basename pero extensión .pdf.
    Usamos un perfil de usuario temporal por invocación para evitar bloqueos
    cuando hay varias conversiones en paralelo.
    """
    soffice = _resolver_soffice()
    os.makedirs(out_dir, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="lo_profile_") as profile_dir:
        cmd = [
            soffice,
            f"-env:UserInstallation=file://{profile_dir.replace(os.sep, '/')}",
            "--headless",
            "--norestore",
            "--nolockcheck",
            "--nologo",
            "--convert-to", "pdf",
            "--outdir", out_dir,
            docx_path,
        ]
        try:
            res = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout
            )
        except subprocess.TimeoutExpired as e:
            raise ConversionError(f"LibreOffice tardó más de {timeout}s") from e

    if res.returncode != 0:
        raise ConversionError(
            f"LibreOffice devolvió código {res.returncode}.\n"
            f"stdout: {res.stdout}\nstderr: {res.stderr}"
        )

    base = os.path.splitext(os.path.basename(docx_path))[0]
    pdf_path = os.path.join(out_dir, f"{base}.pdf")
    if not os.path.exists(pdf_path):
        raise ConversionError(
            f"No se encontró el PDF esperado en {pdf_path}.\n"
            f"stdout: {res.stdout}"
        )
    return pdf_path
