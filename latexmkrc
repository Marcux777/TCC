$out_dir = 'build';
$xelatex = 'xelatex -interaction=nonstopmode -file-line-error %O %S';
$pdf_mode = 5;
$bibtex_use = 1;
ensure_path('BIBINPUTS', '../');
