#!/usr/bin/env python3
"""
Tibia Overlay — espelho de regiões da tela, estilo TibiaVision.

100% passivo: só lê pixels da tela (a mesma coisa que o OBS faz) e desenha
janelas próprias por cima. Não lê memória do cliente, não injeta nada no
processo do Tibia e não envia nenhum input ao jogo.

Uso:
    python overlay.py

Fluxo:
    1. "Nova região" → a tela escurece → arraste um retângulo sobre a parte
       do cliente que você quer espelhar (cooldowns, hotkeys, vida do party…).
    2. Uma janela-espelho aparece ao lado da região. Arraste-a com o botão
       esquerdo para onde quiser.
    3. Botão direito na janela-espelho: travar (o clique passa a atravessar),
       mudar o tamanho ou remover. Destrave pelo painel de controle.
    4. "Salvar layout" grava tudo num JSON para recarregar depois.
"""

import json
import os
import sys
from pathlib import Path

import mss
from PySide6.QtCore import QRect, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

DEFAULT_FPS = 20
BORDER = QColor(255, 127, 0)  # laranja TibiaVision
# Empacotado como app (PyInstaller), __file__ aponta para dentro do bundle,
# que não é lugar de gravar layout — usa a pasta do usuário nesse caso.
if getattr(sys, "frozen", False):
    LAYOUT_DIR = Path.home() / "Documents"
else:
    LAYOUT_DIR = Path(__file__).resolve().parent


class RegionSelector(QWidget):
    """Tela escurecida onde o usuário arrasta um retângulo para escolher a região."""

    picked = Signal(dict)

    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setCursor(Qt.CrossCursor)
        self.setGeometry(QGuiApplication.primaryScreen().virtualGeometry())
        self._origin = None
        self._current = None

    def paintEvent(self, _event):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(0, 0, 0, 90))
        if self._origin is not None:
            r = QRect(self._origin, self._current).normalized()
            p.setCompositionMode(QPainter.CompositionMode_Clear)
            p.fillRect(r, Qt.transparent)
            p.setCompositionMode(QPainter.CompositionMode_SourceOver)
            p.setPen(BORDER)
            p.drawRect(r)

    def mousePressEvent(self, e):
        self._origin = self._current = e.position().toPoint()
        self.update()

    def mouseMoveEvent(self, e):
        if self._origin is not None:
            self._current = e.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, e):
        if self._origin is None:
            return
        r = QRect(self._origin, e.position().toPoint()).normalized()
        self.close()
        if r.width() >= 8 and r.height() >= 8:
            top_left = self.mapToGlobal(r.topLeft())
            self.picked.emit(
                {
                    "left": top_left.x(),
                    "top": top_left.y(),
                    "width": r.width(),
                    "height": r.height(),
                }
            )

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.close()


class MirrorWindow(QWidget):
    """Janela flutuante always-on-top que espelha uma região da tela."""

    def __init__(self, panel, source: dict, fps: int = DEFAULT_FPS):
        super().__init__()
        self.panel = panel
        self.source = source
        self.locked = False
        self._pix = None
        self._drag = None
        try:
            self._sct = mss.mss()
        except Exception:
            self._sct = None  # sem permissão de gravação de tela / sem display
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.resize(source["width"], source["height"])
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self.set_fps(fps)
        self._timer.start()

    def set_fps(self, fps: int):
        self._timer.setInterval(max(1000 // max(fps, 1), 10))

    def _tick(self):
        if self._sct is None or not self.isVisible():
            return
        try:
            g = self._sct.grab(self.source)
        except Exception:
            return  # região fora da tela (monitor desconectado etc.)
        # mss devolve BGRA; em little-endian isso é exatamente o Format_ARGB32.
        # Em telas Retina g.width vem em pixels físicos (2× a região lógica) —
        # o drawPixmap escala para o rect da janela, então funciona dos dois jeitos.
        img = QImage(bytes(g.bgra), g.width, g.height, g.width * 4, QImage.Format_ARGB32)
        self._pix = QPixmap.fromImage(img)
        self.update()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        if self._pix is not None:
            p.drawPixmap(self.rect(), self._pix)
        else:
            p.fillRect(self.rect(), QColor(30, 30, 30))
        if not self.locked:
            p.setPen(BORDER)
            p.drawRect(self.rect().adjusted(0, 0, -1, -1))

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self._drag is not None:
            self.move(e.globalPosition().toPoint() - self._drag)

    def mouseReleaseEvent(self, _event):
        self._drag = None

    def contextMenuEvent(self, e):
        menu = QMenu(self)
        act_lock = menu.addAction("Travar (clique atravessa; destrave pelo painel)")
        scale = menu.addMenu("Tamanho")
        for pct in (50, 75, 100, 150, 200):
            scale.addAction(
                f"{pct}%",
                lambda pct=pct: self.resize(
                    self.source["width"] * pct // 100,
                    self.source["height"] * pct // 100,
                ),
            )
        act_close = menu.addAction("Remover")
        chosen = menu.exec(e.globalPos())
        if chosen is act_lock:
            self.set_locked(True)
        elif chosen is act_close:
            self.panel.remove_mirror(self)

    def set_locked(self, locked: bool):
        self.locked = locked
        # WindowTransparentForInput = a janela vira "fantasma": cliques passam
        # direto para o que estiver embaixo. Precisa de show() para reaplicar.
        self.setWindowFlag(Qt.WindowTransparentForInput, locked)
        self.show()
        self.panel.refresh_list()


class ControlPanel(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Tibia Overlay")
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        self.mirrors: list[MirrorWindow] = []
        self._selector = None

        central = QWidget()
        layout = QVBoxLayout(central)

        row = QHBoxLayout()
        btn_new = QPushButton("Nova região")
        btn_new.clicked.connect(self.pick_region)
        row.addWidget(btn_new)
        row.addWidget(QLabel("FPS:"))
        self.fps = QSpinBox()
        self.fps.setRange(5, 60)
        self.fps.setValue(DEFAULT_FPS)
        self.fps.valueChanged.connect(self._apply_fps)
        row.addWidget(self.fps)
        layout.addLayout(row)

        self.listw = QListWidget()
        layout.addWidget(self.listw)

        row2 = QHBoxLayout()
        for text, fn in (
            ("Travar/destravar", self.toggle_selected),
            ("Remover", self.remove_selected),
        ):
            b = QPushButton(text)
            b.clicked.connect(fn)
            row2.addWidget(b)
        layout.addLayout(row2)

        row3 = QHBoxLayout()
        for text, fn in (
            ("Salvar layout", self.save_layout),
            ("Carregar layout", self.load_layout),
        ):
            b = QPushButton(text)
            b.clicked.connect(fn)
            row3.addWidget(b)
        layout.addLayout(row3)

        hint = QLabel(
            "Arraste a janela-espelho com o botão esquerdo.\n"
            "Botão direito nela: travar / tamanho / remover.\n"
            "Rode o Tibia em janela (não fullscreen nativo)."
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.setCentralWidget(central)
        self.resize(340, 360)

    # ---- regiões ----------------------------------------------------------

    def pick_region(self):
        self._selector = RegionSelector()
        self._selector.picked.connect(self.add_mirror)
        self._selector.show()
        self._selector.raise_()
        self._selector.activateWindow()

    def add_mirror(self, source, pos=None, size=None, locked=False):
        m = MirrorWindow(self, source, self.fps.value())
        if size:
            m.resize(*size)
        if pos:
            m.move(*pos)
        else:
            # Desloca para fora da região de origem: espelho sobre a própria
            # origem cria efeito de túnel infinito.
            m.move(source["left"] + source["width"] + 20, source["top"])
        m.show()
        if locked:
            m.set_locked(True)
        self.mirrors.append(m)
        self.refresh_list()

    def remove_mirror(self, m: MirrorWindow):
        m.close()
        if m in self.mirrors:
            self.mirrors.remove(m)
        self.refresh_list()

    def refresh_list(self):
        self.listw.clear()
        for i, m in enumerate(self.mirrors, 1):
            state = "travada" if m.locked else "livre"
            self.listw.addItem(
                f"Região {i} — {m.source['width']}×{m.source['height']} ({state})"
            )

    def _selected(self):
        i = self.listw.currentRow()
        return self.mirrors[i] if 0 <= i < len(self.mirrors) else None

    def toggle_selected(self):
        m = self._selected()
        if m:
            m.set_locked(not m.locked)

    def remove_selected(self):
        m = self._selected()
        if m:
            self.remove_mirror(m)

    def _apply_fps(self, v: int):
        for m in self.mirrors:
            m.set_fps(v)

    # ---- layouts ----------------------------------------------------------

    def save_layout(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Salvar layout", str(LAYOUT_DIR / "layout.json"), "JSON (*.json)"
        )
        if not path:
            return
        data = {
            "fps": self.fps.value(),
            "regions": [
                {
                    "source": m.source,
                    "pos": [m.x(), m.y()],
                    "size": [m.width(), m.height()],
                    "locked": m.locked,
                }
                for m in self.mirrors
            ],
        }
        Path(path).write_text(json.dumps(data, indent=2))

    def load_layout(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Carregar layout", str(LAYOUT_DIR), "JSON (*.json)"
        )
        if not path:
            return
        try:
            data = json.loads(Path(path).read_text())
        except (OSError, json.JSONDecodeError) as exc:
            QMessageBox.warning(self, "Tibia Overlay", f"Não consegui ler o layout:\n{exc}")
            return
        for m in list(self.mirrors):
            self.remove_mirror(m)
        self.fps.setValue(int(data.get("fps", DEFAULT_FPS)))
        for r in data.get("regions", []):
            self.add_mirror(
                r["source"],
                pos=r.get("pos"),
                size=r.get("size"),
                locked=r.get("locked", False),
            )

    def closeEvent(self, e):
        for m in list(self.mirrors):
            m.close()
        e.accept()
        QApplication.quit()


def _fix_qt_plugin_path():
    """Contorna o PySide6 não achar o plugin de plataforma ("cocoa" no macOS,
    "windows" no Windows) quando a autodetecção do caminho de plugins falha —
    sintoma: 'Could not find the Qt platform plugin "cocoa" in ""'."""
    if os.environ.get("QT_QPA_PLATFORM_PLUGIN_PATH"):
        return
    import PySide6

    plugins = Path(PySide6.__file__).resolve().parent / "Qt" / "plugins"
    if (plugins / "platforms").is_dir():
        os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = str(plugins / "platforms")


def main():
    _fix_qt_plugin_path()
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # fechar um espelho não encerra o app
    panel = ControlPanel()
    panel.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
