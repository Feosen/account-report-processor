import csv
import locale
import logging
from dataclasses import dataclass
from decimal import Decimal
from functools import partial
from typing import Union, Callable, Any, List, TextIO

from parser import BaseCfg, SrcColCfg, RowData, ValidationError

_logger = logging.getLogger(__name__)


@dataclass
class DstColCfg(BaseCfg):
    id: int
    label: str = None
    value: Union[SrcColCfg, Callable[[RowData], Any]] = None
    visible: bool = True
    filter: Callable[[Any], bool] = None

    def __hash__(self) -> int:
        return self.id

    def clean(self) -> None:
        super().clean()
        if not isinstance(self.value, SrcColCfg) and not hasattr(self.value, '__call__'):
            raise ValidationError(f"value {self.value} не поддерживается.")
        if self.filter is not None and not isinstance(self.value, SrcColCfg):
            raise ValidationError(f"Неверный тип value для filter.")

    class Factory:
        id: int = 1

        @staticmethod
        def factory(**kwargs) -> 'DstColCfg':
            id = DstColCfg.Factory.id
            DstColCfg.Factory.id += 1
            return DstColCfg(id=id, **kwargs)


@dataclass
class DstCfg(BaseCfg):
    postfix: str
    columns: List[DstColCfg]

    def clean(self) -> None:
        super().clean()
        for c in self.columns:
            c.clean()


class Report:
    cfg: DstCfg
    _filter: Callable[[RowData], bool]
    _values_row: Callable[[RowData], List[Any]]

    def __init__(self, cfg: DstCfg) -> None:
        cfg.clean()
        self.cfg = cfg

        filters = []
        for column in cfg.columns:
            if column.filter is not None:
                filters.append((column.value, column.filter))

        def _filter(row: RowData) -> bool:
            return all(map(lambda c: c[1](row[c[0]]), filters))
        self._filter = _filter

        values = []
        for column in cfg.columns:
            if not column.visible:
                continue
            format_fn = None
            if isinstance(column.value, SrcColCfg):
                value_fn = partial(self._default_getter, column=column.value)
                if column.value.data_type in (Decimal, float, int):
                    format_fn = self._numeric_to_s
            elif hasattr(column.value, '__call__'):
                value_fn = column.value
                format_fn = self._numeric_to_s
            else:
                raise ValueError("UNDEFINED")
            if format_fn is not None:
                value_fn = partial(self._default_formatter, value_fn=value_fn, format_fn=format_fn)
            values.append(value_fn)

        def _values_row(row: RowData) -> List[Any]:
            return [v(row) for v in values]
        self._values_row = _values_row

    @staticmethod
    def _numeric_to_s(v: Any) -> str:
        if isinstance(v, (Decimal, float, int)):
            return locale.str(v)
        return str(v)

    @staticmethod
    def _default_formatter(row: RowData, value_fn: Callable[[RowData], Any], format_fn: Callable[[Any], str]) -> str:
        return format_fn(value_fn(row))

    @staticmethod
    def _default_getter(row: RowData, column: SrcColCfg) -> Any:
        return row[column]

    def write(self, out_file: TextIO, rows: List[RowData], with_headers: bool = True) -> None:
        _logger.info(f"Locale LC_NUMERIC: {locale.getlocale(locale.LC_NUMERIC)}")
        writer = csv.writer(out_file, delimiter=';')
        if with_headers:
            headers = [c.label for c in self.cfg.columns if c.visible]
            writer.writerow(headers)
        for row in rows:
            if self._filter(row):
                writer.writerow(self._values_row(row))
            else:
                _logger.info(f"Пропускаю: {row}.")
