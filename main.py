from decimal import Decimal
from pathlib import Path
from typing import List

from parser import SrcColCfg, Parser, SrcCfg
from report import DstColCfg, DstCfg, Report

# Описание входного файла

S_DATE = SrcColCfg.Factory.factory(label='Дата операции')
# Исключаем FAILED
S_STATUS = SrcColCfg.Factory.factory(label='Статус', filter=lambda x: x != 'FAILED')
S_VALUE = SrcColCfg.Factory.factory(label='Сумма операции', data_type=Decimal)
# Оставляем только рубли
S_CURRENCY = SrcColCfg.Factory.factory(label='Валюта операции', filter=lambda x: x == 'RUB')
S_BONUS = SrcColCfg.Factory.factory(label='Бонусы (включая кэшбэк)', data_type=Decimal)
S_CATEGORY = SrcColCfg.Factory.factory(label='Категория')
S_DESC = SrcColCfg.Factory.factory(label='Описание')

src_cfg = SrcCfg([S_DATE, S_STATUS, S_VALUE, S_CURRENCY, S_BONUS, S_CATEGORY, S_DESC])

# Описание выходных файлов

# date, value, bonus -> value + bonus, category (not in trans), desc

D_DATE = DstColCfg.Factory.factory(label=S_DATE.label, value=S_DATE)
D_VALUE = DstColCfg.Factory.factory(label=S_VALUE.label, value=S_VALUE)
D_BONUS = DstColCfg.Factory.factory(label=S_BONUS.label, value=S_BONUS)
D_SUM = DstColCfg.Factory.factory(label='Сумма', value=lambda x: x[S_VALUE] + x[S_BONUS])

category_gain = ['Процентный доход', 'Бонусы', 'Проценты']
category_trans = ['Переводы']
category_t_g = category_trans + category_gain
D_CATEGORY_GAIN = DstColCfg.Factory.factory(label=S_CATEGORY.label, value=S_CATEGORY, filter=lambda x: x in category_gain)
D_CATEGORY_TRANS = DstColCfg.Factory.factory(label=S_CATEGORY.label, value=S_CATEGORY, visible=False, filter=lambda x: x in category_trans)
D_CATEGORY = DstColCfg.Factory.factory(label=S_CATEGORY.label, value=S_CATEGORY, filter=lambda x: x not in category_t_g)
D_DESC = DstColCfg.Factory.factory(label=S_DESC.label, value=S_DESC)
D_BANK = DstColCfg.Factory.factory(label='Банк', value=lambda x: 'Тинькофф')


report_cfgs: List[DstCfg] = [
    DstCfg('loss', [D_DATE, D_SUM, D_VALUE, D_BONUS, D_CATEGORY, D_DESC, D_BANK]),
    DstCfg('transfer', [D_DATE, D_VALUE, D_BONUS, D_SUM, D_CATEGORY_TRANS]),
    DstCfg('gain', [D_DATE, D_VALUE, D_BONUS, D_SUM, D_CATEGORY_GAIN]),
]


def process_file(p: Path) -> None:
    with p.open() as in_file:
        parser = Parser(src_cfg)
        data = parser.parse(in_file)
    for cfg in report_cfgs:
        r = Report(cfg)
        name, ext = p.name.split('.', 1)
        new_name = f'{name}_{cfg.postfix}.{ext}'
        new_p = p.parent / new_name
        with new_p.open('w+', newline='\n') as out_file:
            r.write(out_file, data)


if __name__ == '__main__':
    process_file(Path('in.csv'))
