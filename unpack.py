#!/usr/bin/env python3

"""
long - 32bit (4 butes)

struct FATRecord
{
  char Filename[32];
  long Type;
  long Size;
  long Offset;
};
где:
Filename - имя файла, потом идет один пробел (символ с кодом 00h),
затем все забивается символами = (CDh) => для имени отводится 32 байта;
Type - если 0xCDCDCD00, то это файл, если 0xCDCDCD01 - каталог, 0xCDCDCDFF - метка конца каталога;
Size - размер файла; если каталог, то равен 0;
Offset - положение файла/каталога относительно начала dir файла.

http://www.extractor.ru/articles/opisanie_formatov_dir_i_pck/
"""

import os
import struct


class dirPack(object):
    filename = ""

    fmt = "32sIII"

    t_file = 0xCDCDCD00  # Файл
    t_dir = 0xCDCDCD01  # Каталог
    t_edir = 0xCDCDCDFF  # метка конца каталога

    fin = None
    current_dir = None  # Текущая директория (при распаковке)

    def __init__(self, filename):
        """
        filename - имя файла для распаковки/запаковки
        """
        self.filename = filename

    def unpack(self):
        """
        Распаковать указанный файл
        """
        self.current_dir = os.path.dirname(os.path.realpath(self.filename))

        with open(self.filename, "rb") as fin:
            self.fin = fin
            self._read2(fin)

    def _read2(self, fin, start_seek=None):
        if not start_seek is None:
            fin.seek(start_seek)

        while True:
            name, t, s, offset = struct.unpack(
                self.fmt, fin.read(struct.calcsize(self.fmt))
            )
            name = name[: name.find("\0")]

            c_seek = fin.tell()

            if t == self.t_edir:
                break

            if t == self.t_dir:
                # function work with directory
                pred_dir = self.current_dir
                p = os.path.join(pred_dir, name)
                if not os.path.exists(p):
                    os.makedirs(p)
                self.current_dir = p

                self._read2(fin, offset)

                self.current_dir = pred_dir

            if t == self.t_file:
                # function work with file
                self._crFile(fin, name, s, offset)

                self._rfile(fin)
                break

            fin.seek(c_seek)

        # exit

    def _rfile(self, fin):
        while True:
            name, t, s, offset = struct.unpack(
                self.fmt, fin.read(struct.calcsize(self.fmt))
            )
            name = name[: name.find("\0")]

            if t == self.t_edir:
                break

            if t == self.t_file:
                # function work with file
                self._crFile(fin, name, s, offset)

    def _crFile(self, fin, name, s, offset):
        c_seek = fin.tell()

        fin.seek(offset)
        dt = fin.read(s)

        p = os.path.join(self.current_dir, name)
        with open(p, "wb") as fout:
            fout.write(dt)

        fin.seek(c_seek)

    # ----------------

    def pack(self, d):
        """
        Запаковать указанный каталог в файл
        d - каталог, который нужно упаковать
        """
        self.current_dir = os.path.realpath(d)

        headerLen = (
            self.countItemHeader(self.current_dir) + 1
        ) * struct.calcsize(self.fmt)

        with open(self.filename, "wb") as fout:
            self.fout = fout

            self.sk_file_offset = (
                headerLen  # смещение на место куда надо писать следующий файл
            )

            root_dir = self.current_dir

            # Формируем корневую запись
            name = self._getFmtStrName(os.path.basename(root_dir))

            # начальное смещение для текущих записей
            offset = 0
            # количество записей в структуре для данного каталога
            cnt_entery = 2
            # Следующее свободное смещение
            offset_next = offset + cnt_entery * struct.calcsize(self.fmt)

            fout.write(struct.pack(self.fmt, name, self.t_dir, 0, offset_next))
            fout.write(
                struct.pack(
                    self.fmt,
                    self._getFmtStrName("DIRECTOR.FIN"),
                    self.t_edir,
                    0,
                    0xFF,
                )
            )

            self._makeStructDir(root_dir, offset_next)

    def countItemHeader(self, d):
        cListDir = (
            0  # Количество спискок (директорий у них есть начало и конец)
        )
        cFile = 0  # Общее количество файлов
        for item in os.walk(d):
            cListDir += 1
            cFile += len(item[2])

        res = cListDir * 2 + cFile
        return res

    def getDirFiles(self, d):
        """
        Получаем кортеж директорий и файлов для указанной директории
        """
        files = []
        dirs = []

        for f in os.listdir(d):
            if os.path.isfile(os.path.join(d, f)):
                files.append(f)
            else:
                dirs.append(f)

        return (dirs, files)

    def _getFmtStrName(self, name):
        """
        Получаем имя фвйла в формате уже готовом для упаковки и записи в файл
        """
        if len(name) > 32:
            raise ValueError("Длина строки слишком большая")

        if len(name) < 32:
            name = name + "\0"
            name = name + chr(0xCD) * (32 - len(name))

        return name

    def _makeStructDir(self, root_dir, offset):
        """
        Формирует структуру для указанного каталога и возвращает
        смещение куда она была записана
        offset - откуда начинается свободное место для записей
                 (начальное смещение для текущих записей)
        """

        dirs, files = self.getDirFiles(root_dir)

        # количество записей в структуре для данного каталога
        cnt_entery = len(dirs) + len(files) + 1
        # Следующее свободное смещение (абсолютное значение)
        offset_next = offset + cnt_entery * struct.calcsize(self.fmt)

        dirs, files = self.getDirFiles(root_dir)

        listStruct = []
        for ditem in dirs:
            name = self._getFmtStrName(os.path.basename(ditem))
            listStruct.append(
                struct.pack(self.fmt, name, self.t_dir, 0, offset_next)
            )
            offset_next = self._makeStructDir(
                os.path.join(root_dir, ditem), offset_next
            )

        for fitem in files:
            name = self._getFmtStrName(os.path.basename(fitem))

            size = self._makeStructFile(
                os.path.join(root_dir, fitem), self.sk_file_offset
            )
            p_of = self.sk_file_offset
            self.sk_file_offset = self.sk_file_offset + size

            listStruct.append(
                struct.pack(self.fmt, name, self.t_file, size, p_of)
            )

        listStruct.append(
            struct.pack(
                self.fmt,
                self._getFmtStrName("DIRECTOR.FIN"),
                self.t_edir,
                0,
                0xFF,
            )
        )

        # Записываем полученную структуру в файл в нужное место
        self.fout.seek(offset)
        for item in listStruct:
            self.fout.write(item)

        return offset_next

    def _makeStructFile(self, file_path, offset):
        """
        Записывает указанный файл по переданному смещению
        Возвращает размер записанных данных
        """

        with open(file_path, "rb") as fin:
            fileContent = fin.read()

        size = len(fileContent)

        self.fout.seek(offset)
        self.fout.write(fileContent)

        return size


if __name__ == "__main__":

    import sys
    import argparse

    parser = argparse.ArgumentParser()

    subparsers = parser.add_subparsers(help="Список команд", dest="sbname")
    parser_u = subparsers.add_parser("u", help="Распаковать указанный файл")
    parser_p = subparsers.add_parser(
        "p", help="Запаковать указанный каталог в файл"
    )

    parser_u.add_argument(
        "-f",
        action="store",
        required=True,
        help="Название файла, который будет распакован в текущию директорию",
    )

    parser_p.add_argument(
        "-d",
        action="store",
        required=True,
        help="Название каталога, который нужно запаковать",
    )
    parser_p.add_argument(
        "-f",
        action="store",
        required=True,
        help="Имя файла, в который будет записан архив",
    )

    args = parser.parse_args()

    if args.sbname == "u":
        print("Распаковываем...")
        s = dirPack(args.f)
        s.unpack()

    if args.sbname == "p":
        print("Запаковываем...")

        if not os.path.exists(args.d):
            print('[E] Директории "{}", для упаковки не найдено'.format(
                args.d)
            )
            sys.exit(1)

        if os.path.isfile(args.f):
            print('[E] Файл "{}" уже существует'.format(args.f))
            sys.exit(1)

        s = dirPack(args.f)
        s.pack(args.d)
