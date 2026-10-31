"""Offline report for the LAMP-inspired modal correlation experiment."""
import json
from pathlib import Path


def write_lamp_report(output,result):
    source=Path(__file__).parent
    # Reuse the established report design system, not its coupler-specific UI.
    standard=(source/'report_template.html').read_text(encoding='utf-8')
    css=standard.split('<style>')[1].split('</style>')[0]
    template=(source/'lamp_report_template.html').read_text(encoding='utf-8')
    script=(source/'lamp_report_ui.js').read_text(encoding='utf-8')
    data=json.dumps(result,ensure_ascii=False,allow_nan=False,separators=(',',':')).replace('<','\\u003c')
    (output/'index.html').write_text(template.replace('@@CSS@@',css).replace('@@DATA@@',data).replace('@@SCRIPT@@',script),encoding='utf-8')
