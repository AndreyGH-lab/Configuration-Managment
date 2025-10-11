import os
import getpass
import socket
import platform
from vfs import VirtualFileSystem, VFSException, format_mode


class ShellEmulator:
    def __init__(self, prompt_template="{user}@{host}:{cwd}$ ", vfs_path=None):
        # Инициализация эмулятора: имя пользователя, хост и виртуальная ФС
        self.user = getpass.getuser()
        self.host = socket.gethostname().split(".", 1)[0]
        self.prompt_template = prompt_template
        self.running = True
        self.vfs = None
        # Попытка загрузить VFS из CSV
        if vfs_path and os.path.exists(vfs_path):
            try:
                self.vfs = VirtualFileSystem(vfs_path)
                print(f"[INFO] VFS loaded successfully from {vfs_path}")
            except Exception as e:
                print(f"[ERROR] Failed to load VFS: {e}")

    def format_prompt(self):
        # Формирует приглашение к вводу (username@host:cwd$)
        cwd_display = self.vfs.cwd if self.vfs else "~"
        return self.prompt_template.format(user=self.user, host=self.host, cwd=cwd_display)

    #  команды
    def cmd_ls(self, args):
        # Вывод содержимого каталога (опционально с режимом -l)
        if not self.vfs:
            print("[stub] ls")
            return
        if args and args[0] == "-l":
            try:
                node = self.vfs._get_node(self.vfs.cwd)
                for name in sorted(node.children.keys()):
                    entry = node.children[name]
                    print(f"{format_mode(entry.mode)} {name}")
            except VFSException as e:
                print(f"ls: {e}")
        else:
            try:
                print("  ".join(self.vfs.ls()))
            except VFSException as e:
                print(f"ls: {e}")

    def cmd_cd(self, args):
        # Переход в указанный каталог
        if not self.vfs:
            print("[stub] cd")
            return
        target = args[0] if args else "/"
        try:
            self.vfs.cd(target)
        except VFSException as e:
            print(f"cd: {e}")

    def cmd_tree(self, args):
        # Рекурсивное отображение структуры каталогов
        if not self.vfs:
            print("[stub] tree")
            return
        try:
            print(self.vfs.tree())
        except VFSException as e:
            print(f"tree: {e}")

    def cmd_vfs_info(self, args):
        # Вывод информации о текущей виртуальной файловой системе
        if not self.vfs:
            print("No VFS loaded.")
            return
        info = self.vfs.vfs_info()
        print(f"VFS file: {info['filename']}")
        print(f"SHA-256 : {info['sha256']}")

    def cmd_uname(self, args):
        # Имитация системной команды uname
        print(f"{platform.system()} {self.host} {platform.release()} Python/{platform.python_version()}")

    def cmd_whoami(self, args):
        # Возвращает имя текущего пользователя
        print(self.user)

    def cmd_chmod(self, args):
        # Изменение прав доступа (chmod MODE PATH)
        if not self.vfs:
            print("No VFS loaded.")
            return
        if len(args) != 2:
            print("Usage: chmod MODE PATH")
            return
        try:
            self.vfs.chmod(args[1], args[0])
        except VFSException as e:
            print(f"chmod: {e}")

    def cmd_rm(self, args):
        # Удаление файлов или каталогов (-r для рекурсивного)
        if not self.vfs:
            print("No VFS loaded.")
            return
        recursive = False
        paths = []
        for a in args:
            if a in ("-r", "-R"):
                recursive = True
            else:
                paths.append(a)
        if not paths:
            print("Usage: rm [-r] PATH ...")
            return
        for p in paths:
            try:
                self.vfs.rm(p, recursive=recursive)
            except VFSException as e:
                print(f"rm: {e}")

    def cmd_exit(self, args):
        # Завершает работу эмулятора
        print("Exiting emulator.")
        self.running = False

    # диспетчер команд
    def run_command(self, cmd, args):
        # Вызывает нужный обработчик по имени команды
        mapping = {
            "ls": self.cmd_ls,
            "cd": self.cmd_cd,
            "tree": self.cmd_tree,
            "vfs-info": self.cmd_vfs_info,
            "uname": self.cmd_uname,
            "whoami": self.cmd_whoami,
            "chmod": self.cmd_chmod,
            "rm": self.cmd_rm,
            "exit": self.cmd_exit,
        }
        if cmd in mapping:
            mapping[cmd](args)
        else:
            print(f"Unknown command: {cmd}")

    def run_script(self, script_path):
        # Выполняет команды из стартового скрипта (startup.txt)
        if not os.path.exists(script_path):
            print(f"[INFO] No startup script found ({script_path})")
            return
        print(f"\n[INFO] Executing startup script: {script_path}\n")
        with open(script_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                print(f"{self.format_prompt()}{line}")
                cmd, *args = line.split()
                self.run_command(cmd, args)
                if not self.running:
                    return
        print("\n[INFO] Startup script finished.\n")

    def repl(self):
        # Основной REPL-цикл (интерактивный режим)
        while self.running:
            try:
                line = input(self.format_prompt())
            except EOFError:
                print()
                break
            if not line.strip():
                continue
            cmd, *args = line.split()
            self.run_command(cmd, args)


def main():
    # Точка входа: загрузка VFS и запуск скрипта / REPL
    vfs_path = os.path.join(os.getcwd(), "vfs_nested.csv")
    emulator = ShellEmulator(vfs_path=vfs_path)
    startup = os.path.join(os.getcwd(), "startup.txt")
    emulator.run_script(startup)
    if emulator.running:
        emulator.repl()


if __name__ == "__main__":
    main()
