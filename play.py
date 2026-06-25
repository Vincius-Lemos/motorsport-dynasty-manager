"""
Ponto de entrada da interface gráfica do Motorsport Dynasty Manager.
Rode com:  python play.py
"""
from gui.app import App
from gui.scenes import MenuScene


def main():
    app = App()
    app.push(MenuScene(app))
    app.run()


if __name__ == "__main__":
    main()
