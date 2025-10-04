import os
import sys
import getpass
import socket


class ShellEmulator:
    def __init__(self, prompt_template="{user}@{host}:{cwd}$ "):
        # реальные данные ОС
        self.user = getpass.getuser()
        # короткое hostname (до первой точки)
        self.host = socket.gethostname().split(".", 1)[0]
        # виртуальная текущая директория (не трогаем реальную FS)
        self.cwd = os.getcwd()
        self.home = os.path.expanduser("~")
        self.prompt_template = prompt_template
        self.running = True

    def _shorten_cwd(self, path: str) -> str:
        """Показывает путь с заменой домашней директории на ~"""
        if path == self.home or path.startswith(self.home + os.sep):
            return path.replace(self.home, "~", 1)
        return path

    def format_prompt(self) -> str:
        """Собирает строку приглашения"""
        return self.prompt_template.format(
            user=self.user,
            host=self.host,
            cwd=self._shorten_cwd(self.cwd),
        )

    def parse_input(self, line: str):

        tokens = line.strip().split()
        if not tokens:
            return None, []
        return tokens[0], tokens[1:]

    # ----- команды-заглушки -----
    def cmd_ls(self, args):
        print(f"[stub] ls called with args: {args}")

    def cmd_cd(self, args):
        print(f"[stub] cd called with args: {args}")
        if not args:
            # cd без аргументов -> домой
            self.cwd = self.home
            print(f"(virtual) cwd -> {self.cwd}")
            return

        target = args[0]
        if os.path.isabs(target):
            new = os.path.normpath(target)
        else:
            new = os.path.normpath(os.path.join(self.cwd, target))

        # Мы не проверяем существование, просто сохраняем виртуальный путь
        self.cwd = new
        print(f"(virtual) cwd -> {self.cwd}")

    def cmd_exit(self, args):
        print("Exiting emulator.")
        self.running = False

    def run_command(self, cmd: str, args: list):
        if cmd == "exit":
            self.cmd_exit(args)
        elif cmd == "ls":
            self.cmd_ls(args)
        elif cmd == "cd":
            self.cmd_cd(args)
        else:
            print(f"Unknown command: {cmd!r}")

    def repl(self):
        """Основной цикл REPL"""
        try:
            while self.running:
                try:
                    line = input(self.format_prompt())
                except EOFError:
                    # Ctrl-D / EOF -> выход
                    print()
                    break

                if not line.strip():
                    continue

                cmd, args = self.parse_input(line)
                if cmd is None:
                    continue

                # Выполняем команду (заглушки / обработка ошибок)
                self.run_command(cmd, args)

        except KeyboardInterrupt:
            # Ctrl-C -> красиво завершаем
            print("\nInterrupted. Exiting.")


def main():
    emulator = ShellEmulator()
    emulator.repl()


if __name__ == "__main__":
    main()
