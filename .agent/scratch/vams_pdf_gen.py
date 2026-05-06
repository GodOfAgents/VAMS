import sys
import os
from fpdf import FPDF
import re

class VAMSPDF(FPDF):
    def header(self):
        self.set_fill_color(0, 82, 255) # VAMS Blue
        self.rect(0, 0, 210, 8, 'F')
        self.set_y(12)
        
    def footer(self):
        self.set_y(-15)
        self.set_font('helvetica', 'I', 8)
        self.set_text_color(100)
        self.cell(0, 10, f'VAMS Narrative - Page {self.page_no()}', 0, 0, 'C')

def generate_pdf(markdown_path, output_path):
    pdf = VAMSPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    
    with open(markdown_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Clean content
    content = re.sub(r'<!--.*?-->', '', content, flags=re.DOTALL)
    
    lines = content.split('\n')
    
    pdf.set_font('helvetica', '', 11)
    pdf.set_text_color(50, 50, 50)

    for line in lines:
        # Strip emojis
        line = "".join(c for c in line if ord(c) < 128)
        line = line.strip()
        
        if not line:
            pdf.ln(2)
            continue

        if line.startswith('# '):
            pdf.ln(10)
            pdf.set_font('helvetica', 'B', 22)
            pdf.set_text_color(0, 82, 255)
            pdf.multi_cell(0, 12, line[2:].upper(), align='C')
            pdf.ln(5)
            pdf.set_draw_color(0, 82, 255)
            pdf.line(20, pdf.get_y(), 190, pdf.get_y())
            pdf.ln(10)
            continue
            
        if line.startswith('## '):
            pdf.ln(5)
            pdf.set_font('helvetica', 'B', 16)
            pdf.set_text_color(20, 30, 50)
            pdf.set_fill_color(230, 240, 255)
            pdf.cell(0, 10, line[3:].strip(), ln=True, fill=True)
            pdf.ln(3)
            continue
            
        if line.startswith('### '):
            pdf.ln(3)
            pdf.set_font('helvetica', 'B', 13)
            pdf.set_text_color(0, 82, 255)
            pdf.cell(0, 8, line[4:].strip(), ln=True)
            pdf.ln(2)
            continue
            
        if line.startswith('> '):
            pdf.set_font('helvetica', 'I', 10)
            pdf.set_text_color(80, 80, 80)
            pdf.multi_cell(0, 6, line[2:].strip(), border='L')
            pdf.ln(4)
            continue
            
        if line.startswith('- ') or line.startswith('* '):
            pdf.set_font('helvetica', '', 11)
            pdf.set_text_color(60, 60, 60)
            text = line[2:].strip()
            pdf.multi_cell(0, 6, f"  - {text}")
            pdf.ln(1)
            continue

        # Ignore table separator lines
        if '|---' in line or '---|' in line:
            continue

        # Standard Text / Simple Table row as text
        pdf.set_font('helvetica', '', 11)
        pdf.set_text_color(60, 60, 60)
        clean_line = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', line)
        clean_line = clean_line.replace('**', '').replace('__', '').replace('|', '  ')
        pdf.multi_cell(0, 6, clean_line)
        pdf.ln(1)

    pdf.output(output_path)
    print(f"PDF successfully generated at: {output_path}")

if __name__ == "__main__":
    generate_pdf(sys.argv[1], sys.argv[2])
