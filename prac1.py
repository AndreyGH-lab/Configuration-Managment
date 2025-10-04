import os
import getpass
import socket
import argparse


class ShellEmulator:
    def __init__(self, prompt_template="{user}@{host}:{cwd}$ ", vfs_path=None):
        self.user = getpass.getuser()
        self.host = socket.gethostname().split(".", 1)[0]
        self.cwd = os.getcwd()
        self.home = os.path.expanduser("~")
        self.prompt_template = prompt_template
        self.vfs_path = vfs_path
        self.running = True

    # --- форматирование приглашения ---
    def _shorten_cwd(self, path: str) -> str:
        if path == self.home or path.startswith(self.home + os.sep):
            return path.replace(self.home, "~", 1)
        return path

    def format_prompt(self) -> str:
        return self.prompt_template.format(
            user=self.user,
            host=self.host,
            cwd=self._shorten_cwd(self.cwd)
        )

    # --- парсер команд ---
    def parse_input(self, line: str):
        tokens = line.strip().split()
        if not tokens:
            return None, []
        return tokens[0], tokens[1:]

    # --- команды-заглушки ---
    def cmd_ls(self, args):
        print(f"[stub] ls called with args: {args}")

    def cmd_cd(self, args):
        print(f"[stub] cd called with args: {args}")
        if not args:
            self.cwd = self.home
            print(f"(virtual) cwd -> {self.cwd}")
            return
        target = args[0]
        if os.path.isabs(target):
            new = os.path.normpath(target)
        else:
            new = os.path.normpath(os.path.join(self.cwd, target))
        self.cwd = new
        print(f"(virtual) cwd -> {self.cwd}")

    def cmd_exit(self, args):
        print("Exiting emulator.")
        self.running = False

    # --- выполнение команд ---
    def run_command(self, cmd, args):
        try:
            if cmd == "exit":
                self.cmd_exit(args)
            elif cmd == "ls":
                self.cmd_ls(args)
            elif cmd == "cd":
                self.cmd_cd(args)
            else:
                print(f"Unknown command: {cmd!r}")
        except Exception as e:
            print(f"Error while executing command '{cmd}': {e}")

    # --- выполнение скрипта ---
    def run_script(self, script_path):
        print(f"\n[INFO] Executing startup script: {script_path}\n")
        try:
            with open(script_path, "r", encoding="utf-8") as f:
                for lineno, line in enumerate(f, start=1):
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue  # пропускаем пустые и комментарии
                    print(f"{self.format_prompt()}{line}")
                    cmd, args = self.parse_input(line)
                    if cmd is None:
                        continue
                    try:
                        self.run_command(cmd, args)
                        # если команда exit — прекращаем выполнение скрипта
                        if not self.running:
                            print("[INFO] Script terminated by 'exit' command.\n")
                            return
                    except Exception as e:
                        print(f"[ERROR] Line {lineno}: {e}")
        except FileNotFoundError:
            print(f"[INFO] No startup script found ({script_path}), skipping.")
        except Exception as e:
            print(f"[ERROR] Failed to execute script '{script_path}': {e}")
        print("\n[INFO] Startup script execution finished.\n")

    # --- основной цикл REPL ---
    def repl(self):
        try:
            while self.running:
                try:
                    line = input(self.format_prompt())
                except EOFError:
                    print()
                    break

                if not line.strip():
                    continue

                cmd, args = self.parse_input(line)
                if cmd is None:
                    continue

                self.run_command(cmd, args)

        except KeyboardInterrupt:
            print("\nInterrupted. Exiting.")


def main():
    parser = argparse.ArgumentParser(
        description="Stage 2: Shell emulator with automatic startup script execution."
    )
    parser.add_argument("--vfs-path", help="Path to VFS CSV file", default=None)
    parser.add_argument("--prompt", help="Custom prompt template", default="{user}@{host}:{cwd}$ ")
    args = parser.parse_args()

    print("[DEBUG] Launch configuration:")
    print(f"  VFS path       : {args.vfs_path}")
    print(f"  Prompt template: {args.prompt!r}\n")

    emulator = ShellEmulator(prompt_template=args.prompt, vfs_path=args.vfs_path)

    # --- Автоматический запуск startup.txt ---
    startup_path = os.path.join(os.getcwd(), "startup.txt")
    emulator.run_script(startup_path)

    # --- Если после скрипта эмулятор всё ещё работает — запускаем REPL ---
    if emulator.running:
        emulator.repl()


if __name__ == "__main__":
    main()
