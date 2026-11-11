"""Thème HÔPITAL : clair, vert d'eau / blanc, menu latéral foncé."""

COULEURS = {"principal": "#0f766e", "fonce": "#134e4a", "fond": "#f0f5f4", "carte": "#ffffff",
            "texte": "#1f2937", "danger": "#dc2626", "avertissement": "#f59e0b", "ok": "#16a34a"}

FEUILLE = """
* { font-family: 'Segoe UI', 'Noto Sans', sans-serif; font-size: 13px; color: #1f2937; }
QMainWindow, QStackedWidget > QWidget { background: #f0f5f4; }
#menu { background: #134e4a; border: none; outline: none; min-width: 190px; }
#menu::item { color: #cdeae6; padding: 13px 18px; border-left: 4px solid transparent; }
#menu::item:selected { background: #0f766e; color: white; border-left: 4px solid #5eead4; }
#titreMenu { background: #134e4a; color: white; font-size: 17px; font-weight: bold; padding: 18px; }
QGroupBox { background: white; border: 1px solid #d5e3e1; border-radius: 8px; margin-top: 14px; padding: 14px 10px 8px 10px; font-weight: bold; }
QGroupBox::title { subcontrol-origin: margin; left: 12px; color: #0f766e; }
QPushButton { background: #0f766e; color: white; border: none; border-radius: 6px; padding: 7px 16px; }
QPushButton:hover { background: #115e59; }
QPushButton[secondaire="true"] { background: #e2efed; color: #0f766e; }
QPushButton[danger="true"] { background: #dc2626; }
QLineEdit, QComboBox, QDateTimeEdit, QDateEdit, QTextBrowser {
    background: white; border: 1px solid #b9cfcc; border-radius: 5px; padding: 4px 6px; }
QTableWidget { background: white; alternate-background-color: #f4faf9; border: 1px solid #d5e3e1; gridline-color: #e5eeec; selection-background-color: #99e6dc; selection-color: #134e4a; }
QHeaderView::section { background: #0f766e; color: white; border: none; padding: 6px; font-weight: bold; }
#btnDemo { background: #0f766e; color: white; margin: 12px; padding: 9px; }
#carte { background: white; border: 1px solid #d5e3e1; border-radius: 10px; }
#carteValeur { font-size: 26px; font-weight: bold; color: #0f766e; }
#carteTitre { color: #6b7f7c; }
#titrePage { font-size: 20px; font-weight: bold; color: #134e4a; }
"""
