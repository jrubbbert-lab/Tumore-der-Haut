#!/usr/bin/env python3
"""
Medizin Lernhelfer – Digitale Tafel-Sicherung für Krankheitsbilder
Entwickelt für Medizin- und Pflegeschüler
"""

import customtkinter as ctk
import anthropic
import json
import os
import sys
import threading
import configparser
import re
from datetime import datetime
from pathlib import Path
from tkinter import messagebox, filedialog

# PDF-Generierung
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table,
    TableStyle, HRFlowable, KeepTogether
)
from reportlab.lib.colors import HexColor, black
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY

# ==============================================================
# KONFIGURATION
# ==============================================================
APP_NAME = "Medizin Lernhelfer"
VERSION = "1.0.0"
MODEL_ID = "claude-opus-4-5"

DISEASES = [
    "Malignes Melanom",
    "Plattenepithelkarzinom der Haut",
    "Basalzellkarzinom",
]

CATEGORIES = [
    "1. Definition",
    "2. Pathophysiologie",
    "3. Ätiologie",
    "4. Symptome",
    "5. Diagnose",
    "6. Differenzialdiagnose",
    "7. Therapie",
    "8. Komplikationen",
    "9. Prognose",
]

CONFIG_FILE = Path.home() / ".medizin_lernhelfer" / "config.ini"

# Farben
C_PRIMARY    = "#2B4C7E"
C_SECONDARY  = "#567EBB"
C_SUCCESS    = "#2E7D32"
C_WARNING    = "#CC4400"
C_BG         = "#F5F7FA"
C_WHITE      = "#FFFFFF"
C_STUDENT    = "#EBF5FB"
C_STUDENT_BD = "#7BBFD4"
C_REVISED    = "#F0FFF4"
C_REVISED_BD = "#7BC47B"
C_MISSING_BG = "#FFF8F0"
C_MISSING_BD = "#FFAA80"
C_TEXT       = "#1A1A1A"
C_MUTED      = "#666666"


# ==============================================================
# CONFIG-MANAGER
# ==============================================================
class ConfigManager:
    def __init__(self):
        self.config = configparser.ConfigParser()
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        if CONFIG_FILE.exists():
            self.config.read(CONFIG_FILE, encoding="utf-8")
        if "Settings" not in self.config:
            self.config["Settings"] = {}

    def get_api_key(self) -> str:
        return self.config["Settings"].get("api_key", "")

    def save_api_key(self, key: str):
        self.config["Settings"]["api_key"] = key
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            self.config.write(f)


# ==============================================================
# WISSENSBASIS LADEN
# ==============================================================
def load_knowledge_base() -> str | None:
    kb_path = Path(__file__).parent / "knowledge_base.txt"
    if not kb_path.exists():
        return None
    content = kb_path.read_text(encoding="utf-8")
    # Nur Platzhalter vorhanden?
    lines = [l for l in content.splitlines() if l.strip() and not l.strip().startswith("#")]
    if not lines:
        return None
    return content


# ==============================================================
# CLAUDE-API-ANALYSE
# ==============================================================
def analyze_with_claude(
    api_key: str,
    disease: str,
    category: str,
    student_text: str,
    knowledge_base: str | None,
) -> dict:
    client = anthropic.Anthropic(api_key=api_key)

    if knowledge_base:
        kb_block = (
            "\n\nWISSENSBASIS (einzige erlaubte Quelle):\n"
            "==========================================\n"
            f"{knowledge_base}\n"
            "==========================================\n"
        )
        kb_instruction = (
            "WICHTIG: Nutze AUSSCHLIESSLICH die obige Wissensbasis als fachliche Quelle. "
            "Füge KEIN Wissen hinzu, das nicht dort enthalten ist. "
            "Wenn ein Aspekt in der Wissensbasis nicht vorkommt, lasse ihn weg."
        )
    else:
        kb_block = ""
        kb_instruction = (
            "Nutze dein medizinisches Fachwissen als Quelle. "
            "Bleibe auf dem Niveau einer Pflegeausbildung."
        )

    prompt = f"""Du bist eine erfahrene Medizin-/Pflegelehrkraft.
{kb_instruction}{kb_block}
ERKRANKUNG: {disease}
KATEGORIE: {category}

SCHÜLERANTWORT:
\"\"\"{student_text}\"\"\"

Aufgabe:
1. Prüfe, welche fachlich wichtigen Aspekte fehlen oder inhaltlich falsch sind.
2. Erstelle eine überarbeitete Version: Behalte die Formulierungen der Schüler so weit wie möglich bei. Ergänze nur das Wesentliche, korrigiere sachliche Fehler. Die Schülerarbeit soll erkennbar bleiben.

Antworte NUR im folgenden JSON-Format (kein Markdown-Block, reines JSON):
{{
  "fehlende_aspekte": "Aufzählung der fehlenden/unvollständigen Punkte als fließenden Text. Falls alle wesentlichen Aspekte vorhanden sind: 'Alle wesentlichen Aspekte wurden erfasst.'",
  "ueberarbeitete_version": "Überarbeiteter Fließtext, der auf den Schülerformulierungen basiert."
}}"""

    message = client.messages.create(
        model=MODEL_ID,
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text.strip()

    # JSON extrahieren
    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            try:
                result = json.loads(match.group())
            except json.JSONDecodeError:
                result = {
                    "fehlende_aspekte": "Fehler beim Parsen der Antwort. Bitte erneut versuchen.",
                    "ueberarbeitete_version": student_text,
                }
        else:
            result = {
                "fehlende_aspekte": raw,
                "ueberarbeitete_version": student_text,
            }

    return result


# ==============================================================
# PDF-EXPORT
# ==============================================================
def generate_pdf(disease: str, session_data: list, filepath: str):
    doc = SimpleDocTemplate(
        filepath,
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2.5 * cm,
        bottomMargin=2 * cm,
    )

    styles = getSampleStyleSheet()

    def style(name, **kw):
        return ParagraphStyle(name, parent=styles["Normal"], **kw)

    title_st = style(
        "T_Title", fontSize=22, spaceAfter=6,
        textColor=HexColor(C_PRIMARY), alignment=TA_CENTER, fontName="Helvetica-Bold",
    )
    subtitle_st = style(
        "T_Sub", fontSize=12, spaceAfter=16,
        textColor=HexColor(C_MUTED), alignment=TA_CENTER,
    )
    cat_st = style(
        "T_Cat", fontSize=15, spaceBefore=18, spaceAfter=6,
        textColor=HexColor(C_WHITE), fontName="Helvetica-Bold",
    )
    label_st = style(
        "T_Label", fontSize=10, spaceAfter=3,
        textColor=HexColor(C_MUTED), fontName="Helvetica-Bold",
    )
    body_st = style(
        "T_Body", fontSize=12, leading=18,
        textColor=HexColor(C_TEXT),
    )
    missing_st = style(
        "T_Miss", fontSize=11, leading=17,
        textColor=HexColor("#993300"),
    )
    footer_st = style(
        "T_Footer", fontSize=8,
        textColor=HexColor("#AAAAAA"), alignment=TA_CENTER,
    )

    COL = 16 * cm

    def colored_box(text, bg_hex, border_hex, text_style):
        safe = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        safe = safe.replace("\n", "<br/>")
        tbl = Table([[Paragraph(safe, text_style)]], colWidths=[COL])
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), HexColor(bg_hex)),
            ("BOX", (0, 0), (-1, -1), 1, HexColor(border_hex)),
            ("PADDING", (0, 0), (-1, -1), 10),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        return tbl

    def category_header(text):
        tbl = Table([[Paragraph(text, cat_st)]], colWidths=[COL])
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), HexColor(C_PRIMARY)),
            ("BOX", (0, 0), (-1, -1), 0, black),
            ("PADDING", (0, 0), (-1, -1), 8),
            ("ROUNDEDCORNERS", [6, 6, 6, 6]),
        ]))
        return tbl

    story = []

    # Titel
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph(f"Krankheitsbild: {disease}", title_st))
    story.append(Paragraph(
        f"Unterrichtssicherung · {datetime.now().strftime('%d.%m.%Y')}", subtitle_st
    ))
    story.append(HRFlowable(width="100%", thickness=2, color=HexColor(C_PRIMARY)))
    story.append(Spacer(1, 0.4 * cm))

    # Legende
    legend_data = [[
        Paragraph(
            '<font color="#2B4C7E">■</font> <b>Blau:</b> Schülerantwort &nbsp;&nbsp;&nbsp;'
            '<font color="#2E7D32">■</font> <b>Grün:</b> Überarbeitete Version &nbsp;&nbsp;&nbsp;'
            '<font color="#993300">■</font> <b>Orange:</b> Fehlende Aspekte',
            style("Legend", fontSize=10),
        )
    ]]
    leg_tbl = Table(legend_data, colWidths=[COL])
    leg_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), HexColor("#F0F4F8")),
        ("BOX", (0, 0), (-1, -1), 1, HexColor("#CCCCCC")),
        ("PADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(leg_tbl)
    story.append(Spacer(1, 0.5 * cm))

    # Kategorien
    for cat_data in session_data:
        block = []
        block.append(category_header(cat_data["category"]))
        block.append(Spacer(1, 0.2 * cm))

        student_text = cat_data.get("student_text", "") or "(keine Eingabe)"
        block.append(Paragraph("Schülerantwort:", label_st))
        block.append(colored_box(student_text, C_STUDENT, C_STUDENT_BD, body_st))
        block.append(Spacer(1, 0.2 * cm))

        analysis = cat_data.get("analysis")
        if analysis:
            missing = analysis.get("fehlende_aspekte", "")
            revised = analysis.get("ueberarbeitete_version", "")

            if missing:
                block.append(Paragraph("Fehlende / unvollständige Aspekte:", label_st))
                block.append(colored_box(missing, "#FFF8F0", C_MISSING_BD, missing_st))
                block.append(Spacer(1, 0.2 * cm))

            if revised:
                block.append(Paragraph("Überarbeitete Version:", label_st))
                block.append(colored_box(revised, C_REVISED, C_REVISED_BD, body_st))

        block.append(Spacer(1, 0.4 * cm))
        story.append(KeepTogether(block[:4]))  # Header + Schülertext zusammen halten
        story.extend(block[4:])

    # Footer
    story.append(HRFlowable(width="100%", thickness=1, color=HexColor("#CCCCCC")))
    story.append(Spacer(1, 0.2 * cm))
    story.append(Paragraph(
        f"{APP_NAME} v{VERSION} · {datetime.now().strftime('%d.%m.%Y %H:%M')}",
        footer_st,
    ))

    doc.build(story)


# ==============================================================
# HAUPT-APP
# ==============================================================
class MedizinLernhelfer(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.config_manager = ConfigManager()
        self.knowledge_base = load_knowledge_base()
        self.current_disease: str | None = None
        self.current_cat_idx: int = 0
        self.session_data: list[dict] = []

        # Fenster
        self.title(APP_NAME)
        self.geometry("1140x800")
        self.minsize(960, 640)
        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")

        self._build_shell()
        self._show_welcome()

    # ----------------------------------------------------------
    # SHELL (Header + Content-Bereich)
    # ----------------------------------------------------------
    def _build_shell(self):
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Header
        self._header = ctk.CTkFrame(self, fg_color=C_PRIMARY, height=68, corner_radius=0)
        self._header.grid(row=0, column=0, sticky="ew")
        self._header.grid_propagate(False)
        self._header.columnconfigure(1, weight=1)

        self._header_label = ctk.CTkLabel(
            self._header,
            text=APP_NAME,
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color="white",
        )
        self._header_label.grid(row=0, column=0, padx=22, pady=18, sticky="w")

        self._settings_btn = ctk.CTkButton(
            self._header,
            text="⚙  API-Schlüssel",
            width=150,
            height=36,
            font=ctk.CTkFont(size=13),
            fg_color="#1A3559",
            hover_color=C_SECONDARY,
            corner_radius=8,
            command=self._show_settings,
        )
        self._settings_btn.grid(row=0, column=2, padx=18, pady=16, sticky="e")

        # Content-Container
        self._content = ctk.CTkFrame(self, fg_color=C_BG, corner_radius=0)
        self._content.grid(row=1, column=0, sticky="nsew")
        self._content.grid_rowconfigure(0, weight=1)
        self._content.grid_columnconfigure(0, weight=1)

    def _clear_content(self):
        for w in self._content.winfo_children():
            w.destroy()

    def _set_header(self, text: str):
        self._header_label.configure(text=text)

    # ----------------------------------------------------------
    # WILLKOMMENS-BILDSCHIRM
    # ----------------------------------------------------------
    def _show_welcome(self):
        self._clear_content()
        self._set_header(APP_NAME)

        scroll = ctk.CTkScrollableFrame(self._content, fg_color=C_BG, corner_radius=0)
        scroll.grid(row=0, column=0, sticky="nsew")
        scroll.columnconfigure(0, weight=1)

        # Titel
        ctk.CTkLabel(
            scroll,
            text="Erkrankung auswählen",
            font=ctk.CTkFont(size=30, weight="bold"),
            text_color=C_PRIMARY,
        ).pack(pady=(45, 8))

        ctk.CTkLabel(
            scroll,
            text="Wähle eine Erkrankung, um die strukturierte Erarbeitung zu beginnen.",
            font=ctk.CTkFont(size=16),
            text_color=C_MUTED,
        ).pack(pady=(0, 10))

        # Wissensbasis-Status
        if self.knowledge_base:
            kb_txt = "✓  Wissensbasis (knowledge_base.txt) geladen"
            kb_col = C_SUCCESS
        else:
            kb_txt = "⚠  Keine Wissensbasis – knowledge_base.txt leer oder nicht vorhanden"
            kb_col = C_WARNING

        ctk.CTkLabel(
            scroll, text=kb_txt,
            font=ctk.CTkFont(size=13), text_color=kb_col,
        ).pack(pady=(0, 30))

        # Krankheits-Buttons
        for disease in DISEASES:
            btn = ctk.CTkButton(
                scroll,
                text=disease,
                width=420,
                height=68,
                font=ctk.CTkFont(size=19, weight="bold"),
                fg_color=C_PRIMARY,
                hover_color=C_SECONDARY,
                corner_radius=12,
                command=lambda d=disease: self._start_session(d),
            )
            btn.pack(pady=9)

        # API-Key-Warnung
        if not self.config_manager.get_api_key():
            warn = ctk.CTkFrame(scroll, fg_color="#FFF3E0", corner_radius=10)
            warn.pack(pady=24, padx=60, fill="x")
            ctk.CTkLabel(
                warn,
                text="⚠  Bitte zuerst den Claude API-Schlüssel eingeben  (⚙ oben rechts)",
                font=ctk.CTkFont(size=14),
                text_color=C_WARNING,
                wraplength=620,
            ).pack(padx=18, pady=14)

        ctk.CTkFrame(scroll, fg_color="transparent", height=40).pack()

    # ----------------------------------------------------------
    # SESSION STARTEN
    # ----------------------------------------------------------
    def _start_session(self, disease: str):
        self.current_disease = disease
        self.current_cat_idx = 0
        self.session_data = []
        self._show_category_screen()

    # ----------------------------------------------------------
    # KATEGORIE-BILDSCHIRM
    # ----------------------------------------------------------
    def _show_category_screen(self):
        self._clear_content()
        self._set_header(f"{APP_NAME}  ·  {self.current_disease}")

        total = len(CATEGORIES)
        current_num = self.current_cat_idx + 1
        category = CATEGORIES[self.current_cat_idx]

        # ---- Fortschrittsleiste ----
        prog_frame = ctk.CTkFrame(self._content, fg_color=C_WHITE, height=54, corner_radius=0)
        prog_frame.pack(fill="x")
        prog_frame.pack_propagate(False)

        inner = ctk.CTkFrame(prog_frame, fg_color="transparent")
        inner.pack(fill="x", padx=22, pady=10)

        ctk.CTkLabel(
            inner,
            text=f"Kategorie {current_num} / {total}",
            font=ctk.CTkFont(size=13),
            text_color=C_MUTED,
        ).pack(side="left")

        # Punkte-Fortschritt
        dots_frame = ctk.CTkFrame(inner, fg_color="transparent")
        dots_frame.pack(side="right")
        for i in range(total):
            if i < self.current_cat_idx:
                color = C_SUCCESS
            elif i == self.current_cat_idx:
                color = C_PRIMARY
            else:
                color = "#CCCCCC"
            ctk.CTkLabel(
                dots_frame, text="●",
                font=ctk.CTkFont(size=13), text_color=color, width=18,
            ).pack(side="left", padx=1)

        bar = ctk.CTkProgressBar(self._content, height=5, corner_radius=0)
        bar.pack(fill="x")
        bar.set(current_num / total)
        bar.configure(progress_color=C_SUCCESS, fg_color="#E0E0E0")

        # ---- Scrollbarer Hauptbereich ----
        scroll = ctk.CTkScrollableFrame(self._content, fg_color=C_BG, corner_radius=0)
        scroll.pack(fill="both", expand=True)
        scroll.columnconfigure(0, weight=1)

        # Kategorie-Titel
        ctk.CTkLabel(
            scroll,
            text=category,
            font=ctk.CTkFont(size=28, weight="bold"),
            text_color=C_PRIMARY,
            anchor="w",
        ).pack(fill="x", padx=32, pady=(26, 6))

        ctk.CTkLabel(
            scroll,
            text=f"Erkrankung: {self.current_disease}",
            font=ctk.CTkFont(size=14),
            text_color=C_MUTED,
            anchor="w",
        ).pack(fill="x", padx=32, pady=(0, 12))

        # Eingabefeld
        input_card = ctk.CTkFrame(scroll, fg_color=C_WHITE, corner_radius=12)
        input_card.pack(fill="x", padx=32, pady=(0, 10))

        ctk.CTkLabel(
            input_card,
            text="Schülerantwort eingeben:",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=C_MUTED,
            anchor="w",
        ).pack(fill="x", padx=16, pady=(14, 4))

        self._text_input = ctk.CTkTextbox(
            input_card,
            height=190,
            font=ctk.CTkFont(size=17),
            fg_color=C_STUDENT,
            border_color=C_STUDENT_BD,
            border_width=2,
            wrap="word",
        )
        self._text_input.pack(fill="x", padx=16, pady=(0, 16))
        self._text_input.focus_set()

        # Vorherigen Text wiederherstellen (falls schon bearbeitet)
        if self.current_cat_idx < len(self.session_data):
            saved = self.session_data[self.current_cat_idx].get("student_text", "")
            if saved:
                self._text_input.insert("1.0", saved)

        # ---- Button-Reihe ----
        btn_row = ctk.CTkFrame(scroll, fg_color="transparent")
        btn_row.pack(fill="x", padx=32, pady=(4, 16))

        if self.current_cat_idx > 0:
            ctk.CTkButton(
                btn_row, text="← Zurück", width=120, height=46,
                font=ctk.CTkFont(size=14),
                fg_color=C_WHITE, text_color=C_PRIMARY,
                border_color=C_PRIMARY, border_width=2, hover_color="#EBF5FB",
                command=self._go_back,
            ).pack(side="left", padx=(0, 10))

        self._analyze_btn = ctk.CTkButton(
            btn_row, text="Analysieren  →", width=210, height=46,
            font=ctk.CTkFont(size=15, weight="bold"),
            fg_color=C_PRIMARY, hover_color=C_SECONDARY,
            command=self._analyze_current,
        )
        self._analyze_btn.pack(side="left")

        ctk.CTkButton(
            btn_row, text="Überspringen", width=150, height=46,
            font=ctk.CTkFont(size=13),
            fg_color=C_WHITE, text_color="#999999",
            border_color="#CCCCCC", border_width=1, hover_color="#F5F5F5",
            command=self._skip_category,
        ).pack(side="left", padx=12)

        # Status-Label
        self._status_label = ctk.CTkLabel(
            scroll, text="", font=ctk.CTkFont(size=14), text_color=C_MUTED,
        )
        self._status_label.pack(pady=4)

        # Ergebnisbereich (wird nach Analyse befüllt)
        self._results_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        self._results_frame.pack(fill="x", padx=32, pady=8)

        # Falls schon Analyse vorhanden, sofort anzeigen
        if self.current_cat_idx < len(self.session_data):
            prev = self.session_data[self.current_cat_idx]
            if prev.get("analysis"):
                self._render_results(prev["student_text"], prev["analysis"], already_saved=True)

        ctk.CTkFrame(scroll, fg_color="transparent", height=40).pack()

    # ----------------------------------------------------------
    # ANALYSE STARTEN
    # ----------------------------------------------------------
    def _analyze_current(self):
        student_text = self._text_input.get("1.0", "end-1c").strip()
        if not student_text:
            messagebox.showwarning("Hinweis", "Bitte eine Antwort eingeben.")
            return

        api_key = self.config_manager.get_api_key()
        if not api_key:
            messagebox.showwarning(
                "API-Schlüssel fehlt",
                "Bitte zuerst den Claude API-Schlüssel eingeben\n(⚙ oben rechts).",
            )
            return

        self._analyze_btn.configure(state="disabled", text="⟳  Analysiere …")
        self._status_label.configure(text="Claude analysiert die Antwort – bitte warten …")

        cat = CATEGORIES[self.current_cat_idx]

        def run():
            try:
                result = analyze_with_claude(
                    api_key, self.current_disease, cat,
                    student_text, self.knowledge_base,
                )
                self.after(0, lambda: self._on_analysis_done(student_text, result))
            except anthropic.AuthenticationError:
                self.after(0, lambda: self._on_analysis_error(
                    "Ungültiger API-Schlüssel.\nBitte überprüfe den Schlüssel in den Einstellungen."
                ))
            except Exception as exc:
                self.after(0, lambda: self._on_analysis_error(str(exc)))

        threading.Thread(target=run, daemon=True).start()

    def _on_analysis_done(self, student_text: str, analysis: dict):
        self._analyze_btn.configure(state="normal", text="Neu analysieren  →")
        self._status_label.configure(text="")
        self._save_category(student_text, analysis)
        self._render_results(student_text, analysis)

    def _on_analysis_error(self, msg: str):
        self._analyze_btn.configure(state="normal", text="Analysieren  →")
        self._status_label.configure(text="")
        messagebox.showerror(
            "Fehler bei der Analyse",
            f"Die Analyse konnte nicht durchgeführt werden:\n\n{msg}\n\n"
            "Bitte prüfe den API-Schlüssel und die Internetverbindung.",
        )

    # ----------------------------------------------------------
    # ERGEBNISSE ANZEIGEN
    # ----------------------------------------------------------
    def _render_results(self, student_text: str, analysis: dict, already_saved: bool = False):
        for w in self._results_frame.winfo_children():
            w.destroy()

        # Trennlinie
        ctk.CTkFrame(self._results_frame, fg_color="#CCCCCC", height=2).pack(fill="x", pady=10)

        # Fehlende Aspekte
        miss_card = ctk.CTkFrame(self._results_frame, fg_color=C_MISSING_BG, corner_radius=10)
        miss_card.pack(fill="x", pady=6)
        ctk.CTkLabel(
            miss_card,
            text="Fehlende / unvollständige Aspekte:",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=C_WARNING, anchor="w",
        ).pack(fill="x", padx=16, pady=(14, 4))
        ctk.CTkLabel(
            miss_card,
            text=analysis.get("fehlende_aspekte", "–"),
            font=ctk.CTkFont(size=15),
            text_color="#333333",
            wraplength=950, justify="left", anchor="w",
        ).pack(fill="x", padx=16, pady=(0, 14))

        # Überarbeitete Version
        rev_card = ctk.CTkFrame(self._results_frame, fg_color=C_REVISED, corner_radius=10)
        rev_card.pack(fill="x", pady=6)
        ctk.CTkLabel(
            rev_card,
            text="Überarbeitete Version (aufbauend auf den Schülerformulierungen):",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=C_SUCCESS, anchor="w",
        ).pack(fill="x", padx=16, pady=(14, 4))

        rev_box = ctk.CTkTextbox(
            rev_card, height=150,
            font=ctk.CTkFont(size=15),
            fg_color=C_REVISED, border_width=0, wrap="word",
        )
        rev_box.pack(fill="x", padx=16, pady=(0, 14))
        rev_box.insert("1.0", analysis.get("ueberarbeitete_version", "–"))
        rev_box.configure(state="disabled")

        # Weiter-Button
        nav = ctk.CTkFrame(self._results_frame, fg_color="transparent")
        nav.pack(fill="x", pady=16)

        is_last = self.current_cat_idx == len(CATEGORIES) - 1
        next_txt = (
            "Zusammenfassung & Export  →"
            if is_last
            else f"Weiter: {CATEGORIES[self.current_cat_idx + 1]}  →"
        )
        ctk.CTkButton(
            nav, text=next_txt, width=340, height=50,
            font=ctk.CTkFont(size=16, weight="bold"),
            fg_color=C_SUCCESS, hover_color="#1B5E20",
            command=self._next_category,
        ).pack(side="left")

    # ----------------------------------------------------------
    # DATEN SPEICHERN
    # ----------------------------------------------------------
    def _save_category(self, student_text: str, analysis: dict | None):
        entry = {
            "category": CATEGORIES[self.current_cat_idx],
            "student_text": student_text,
            "analysis": analysis,
        }
        if self.current_cat_idx < len(self.session_data):
            self.session_data[self.current_cat_idx] = entry
        else:
            # Fülle Lücken mit leeren Einträgen
            while len(self.session_data) < self.current_cat_idx:
                self.session_data.append({
                    "category": CATEGORIES[len(self.session_data)],
                    "student_text": "",
                    "analysis": None,
                })
            self.session_data.append(entry)

    # ----------------------------------------------------------
    # NAVIGATION
    # ----------------------------------------------------------
    def _skip_category(self):
        student_text = self._text_input.get("1.0", "end-1c").strip()
        self._save_category(student_text, None)
        self._next_category()

    def _next_category(self):
        if self.current_cat_idx < len(CATEGORIES) - 1:
            self.current_cat_idx += 1
            self._show_category_screen()
        else:
            self._show_summary()

    def _go_back(self):
        if self.current_cat_idx > 0:
            self.current_cat_idx -= 1
            self._show_category_screen()

    # ----------------------------------------------------------
    # ZUSAMMENFASSUNGS-BILDSCHIRM
    # ----------------------------------------------------------
    def _show_summary(self):
        self._clear_content()
        self._set_header(f"{APP_NAME}  ·  {self.current_disease}")

        scroll = ctk.CTkScrollableFrame(self._content, fg_color=C_BG, corner_radius=0)
        scroll.grid(row=0, column=0, sticky="nsew")
        self._content.grid_rowconfigure(0, weight=1)
        self._content.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            scroll,
            text=f"Zusammenfassung: {self.current_disease}",
            font=ctk.CTkFont(size=26, weight="bold"),
            text_color=C_PRIMARY, anchor="w",
        ).pack(fill="x", padx=32, pady=(30, 6))

        analysed = sum(1 for d in self.session_data if d.get("analysis"))
        ctk.CTkLabel(
            scroll,
            text=f"{len(self.session_data)} Kategorien bearbeitet · {analysed} analysiert",
            font=ctk.CTkFont(size=14), text_color=C_MUTED, anchor="w",
        ).pack(fill="x", padx=32, pady=(0, 20))

        for cat_data in self.session_data:
            card = ctk.CTkFrame(scroll, fg_color=C_WHITE, corner_radius=10)
            card.pack(fill="x", padx=32, pady=6)

            hdr = ctk.CTkFrame(card, fg_color=C_PRIMARY, corner_radius=8)
            hdr.pack(fill="x")
            ctk.CTkLabel(
                hdr, text=cat_data["category"],
                font=ctk.CTkFont(size=14, weight="bold"), text_color="white",
            ).pack(anchor="w", padx=12, pady=8)

            body = ctk.CTkFrame(card, fg_color=C_WHITE)
            body.pack(fill="x", padx=12, pady=8)

            preview = cat_data.get("student_text", "")
            if len(preview) > 220:
                preview = preview[:220] + " …"
            ctk.CTkLabel(
                body,
                text="Schülerantwort: " + (preview or "(keine Eingabe)"),
                font=ctk.CTkFont(size=12), text_color="#555555",
                wraplength=880, justify="left", anchor="w",
            ).pack(anchor="w", pady=2)

            ok = cat_data.get("analysis") is not None
            ctk.CTkLabel(
                body,
                text="✓ Analysiert" if ok else "– Ohne Analyse gespeichert",
                font=ctk.CTkFont(size=11),
                text_color=C_SUCCESS if ok else "#999999",
            ).pack(anchor="w", pady=(2, 4))

        # Export-Buttons
        exp_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        exp_frame.pack(pady=30, padx=32, anchor="w")

        ctk.CTkButton(
            exp_frame, text="📄  Als PDF exportieren",
            width=270, height=58,
            font=ctk.CTkFont(size=17, weight="bold"),
            fg_color=C_PRIMARY, hover_color=C_SECONDARY,
            command=self._export_pdf,
        ).pack(side="left", padx=(0, 16))

        ctk.CTkButton(
            exp_frame, text="↩  Neue Erkrankung",
            width=210, height=58,
            font=ctk.CTkFont(size=15),
            fg_color=C_WHITE, text_color=C_PRIMARY,
            border_color=C_PRIMARY, border_width=2, hover_color="#EBF5FB",
            command=self._new_session,
        ).pack(side="left")

        ctk.CTkFrame(scroll, fg_color="transparent", height=40).pack()

    # ----------------------------------------------------------
    # PDF-EXPORT
    # ----------------------------------------------------------
    def _export_pdf(self):
        default = (
            f"{self.current_disease.replace(' ', '_')}"
            f"_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
        )
        path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF-Dateien", "*.pdf")],
            initialfile=default,
            title="PDF speichern",
        )
        if not path:
            return

        try:
            generate_pdf(self.current_disease, self.session_data, path)
            messagebox.showinfo(
                "Export erfolgreich",
                f"Das Schema wurde gespeichert:\n{path}",
            )
        except Exception as exc:
            messagebox.showerror("Exportfehler", f"Fehler beim PDF-Export:\n{exc}")

    def _new_session(self):
        self.current_disease = None
        self.current_cat_idx = 0
        self.session_data = []
        self._show_welcome()

    # ----------------------------------------------------------
    # EINSTELLUNGEN
    # ----------------------------------------------------------
    def _show_settings(self):
        dlg = ctk.CTkToplevel(self)
        dlg.title("API-Schlüssel Einstellungen")
        dlg.geometry("520x300")
        dlg.resizable(False, False)
        dlg.grab_set()
        dlg.focus_force()

        ctk.CTkLabel(
            dlg, text="Claude API-Schlüssel",
            font=ctk.CTkFont(size=20, weight="bold"), text_color=C_PRIMARY,
        ).pack(pady=(28, 8), padx=30, anchor="w")

        ctk.CTkLabel(
            dlg,
            text="Den Schlüssel bekommst du unter console.anthropic.com → API Keys",
            font=ctk.CTkFont(size=13), text_color=C_MUTED,
        ).pack(pady=(0, 16), padx=30, anchor="w")

        entry = ctk.CTkEntry(
            dlg, width=460, height=46, font=ctk.CTkFont(size=14),
            placeholder_text="sk-ant-…", show="*",
        )
        entry.pack(padx=30, pady=4)
        current = self.config_manager.get_api_key()
        if current:
            entry.insert(0, current)

        def _save():
            key = entry.get().strip()
            if not key:
                messagebox.showwarning("Eingabe fehlt", "Bitte einen API-Schlüssel eingeben.")
                return
            self.config_manager.save_api_key(key)
            messagebox.showinfo("Gespeichert", "API-Schlüssel wurde gespeichert.")
            dlg.destroy()
            self._show_welcome()

        ctk.CTkButton(
            dlg, text="Speichern", width=220, height=46,
            font=ctk.CTkFont(size=15, weight="bold"),
            fg_color=C_PRIMARY, hover_color=C_SECONDARY,
            command=_save,
        ).pack(pady=22)

        dlg.bind("<Return>", lambda _: _save())


# ==============================================================
# EINSTIEGSPUNKT
# ==============================================================
def main():
    app = MedizinLernhelfer()
    app.mainloop()


if __name__ == "__main__":
    main()
