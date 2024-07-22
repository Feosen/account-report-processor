import csv
import locale
import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import List, Any, Dict, Callable, Type, Union, TextIO

_logger = logging.getLogger(__name__)


class ValidationError(Exception):
    pass


# Описание классов и т.д.
class BaseCfg(object):

    def clean(self) -> None:
        pass


@dataclass
class SrcColCfg(BaseCfg):
    id: int
    number: int = None  # zero based
    label: str = None
    data_type: Type = str
    filter: Callable[[Any], bool] = None

    def __hash__(self) -> int:
        return self.id

    def parse(self, v: str) -> Any:
        if self.data_type in (Decimal, float, int):
            return self.data_type(locale.atof(v, self.data_type))
        return self.data_type(v)

    def clean(self) -> None:
        super().clean()
        if self.number is None and self.label is None:
            raise ValidationError("Нельзя указывать одновременно number и label как None.")

    class Factory:
        id: int = 1

        @staticmethod
        def factory(**kwargs) -> 'SrcColCfg':
            id = SrcColCfg.Factory.id
            SrcColCfg.Factory.id += 1
            return SrcColCfg(id=id, **kwargs)


class SrcCfg(BaseCfg):
    columns: List[SrcColCfg]
    _has_all_numbers: Union[bool, None] = None

    def __init__(self, columns: List[SrcColCfg]) -> None:
        super().__init__()
        self.columns = columns

    def clean(self) -> None:
        super().clean()
        for c in self.columns:
            c.clean()
        labels = [c.label for c in self.columns]
        if len(labels) != len(set(labels)):
            raise ValidationError("label должны быть уникальны.")
        if self.has_all_numbers:
            numbers = [c.number for c in self.columns]
            if len(numbers) != len(set(numbers)):
                raise ValidationError("number должны быть уникальны")

    @property
    def has_all_numbers(self):
        if self._has_all_numbers is None:
            self._has_all_numbers = all(map(lambda c: c.number is not None, self.columns))
        return self._has_all_numbers

    def update_numbers(self, labels: List[str]):
        self._has_all_numbers = None
        label_map = {label: i for i, label in enumerate(labels)}
        for column in self.columns:
            try:
                column.number = label_map[column.label]
            except KeyError:
                raise ValidationError(f"Нет столбца с \"{column.label}\".")


RowData = Dict[SrcColCfg, Any]


class Parser:
    cfg: SrcCfg
    _filter: Callable[[RowData], bool]

    def __init__(self, cfg: SrcCfg) -> None:
        cfg.clean()
        self.cfg = cfg

        filters = []
        for column in cfg.columns:
            if column.filter is not None:
                filters.append(column)

        def _filter(row: RowData) -> bool:
            return all(map(lambda c: c.filter(row[c]), filters))

        self._filter = _filter

    def parse(self, in_file: TextIO, has_headers: bool = True) -> List[RowData]:
        if not self.cfg.has_all_numbers and not has_headers:
            raise ValidationError("В конфигурации не указаны номера столбцов, в файле нет заголовков"
                                  " - невозможно сопоставить.")
        _logger.info(f"Locale LC_NUMERIC: {locale.getlocale(locale.LC_NUMERIC)}")
        reader = csv.reader(in_file, delimiter=';')
        process_headers = has_headers
        result: List[RowData] = []
        for row in reader:
            if process_headers:
                if not self.cfg.has_all_numbers:
                    self.cfg.update_numbers(row)
                process_headers = False
            else:
                rd = {c: c.parse(row[c.number]) for c in self.cfg.columns}
                if self._filter(rd):
                    result.append(rd)
                else:
                    _logger.info(f"Пропускаю: {row}.")
        return result
