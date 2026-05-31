#!/usr/bin/env Rscript

library(ggplot2)
library(grid)

pequi_dark <- "#2F4F1F"
pequi_green <- "#6F8F2F"
pequi_leaf <- "#4F772D"
pequi_light <- "#EEF6D8"
pequi_gray <- "#D9E2C4"

dir.create("images", recursive = TRUE, showWarnings = FALSE)
output_path <- "images/figura-poder-protocolo.pdf"
tmp_output_path <- tempfile(fileext = ".pdf")
power_curve_path <- "data/power_curve_reference.csv"
power_summary_path <- "data/power_analysis_rhfs_summary.csv"

if (!file.exists(power_curve_path) || !file.exists(power_summary_path)) {
  stop("Execute `python scripts/power_analysis_rhfs.py` antes de gerar a figura.")
}

strata <- data.frame(
  estrato = factor(
    c("Carga baixa", "Média congestão", "Alta congestão"),
    levels = c("Alta congestão", "Média congestão", "Carga baixa")
  ),
  configuracoes = c(4, 12, 56),
  n_efetivo = c(200, 600, 2800)
)
strata$rotulo <- sprintf(
  "%d configurações | n = %s",
  strata$configuracoes,
  format(strata$n_efetivo, big.mark = ".", decimal.mark = ",", scientific = FALSE)
)
strata$rotulo_x <- ifelse(strata$configuracoes >= 50, strata$configuracoes - 1.5, strata$configuracoes + 2.1)
strata$rotulo_hjust <- ifelse(strata$configuracoes >= 50, 1, 0)
strata$rotulo_cor <- ifelse(strata$configuracoes >= 50, "white", pequi_dark)

power_points <- read.csv(power_curve_path, stringsAsFactors = FALSE)
power_points$estrato <- factor(power_points$stratum, levels = c("Média congestão", "Alta congestão"))
power_points$efeito <- power_points$effect_pct
power_points$poder <- power_points$power
power_points <- power_points[order(power_points$estrato, power_points$efeito), ]

power_summary <- read.csv(power_summary_path, stringsAsFactors = FALSE)
medium_mde <- power_summary$mde80_pct[power_summary$stratum == "Média congestão"]
high_mde <- power_summary$mde80_pct[power_summary$stratum == "Alta congestão"]
bootstrap_replicates <- power_summary$bootstrap_replicates[1]
alpha_value <- power_summary$alpha[1]

comma_number <- function(x, digits = 2) {
  formatC(x, format = "f", digits = digits, decimal.mark = ",")
}

integer_pt <- function(x) {
  formatC(x, format = "d", big.mark = ".", decimal.mark = ",")
}

theme_pequi <- function(base_size = 9) {
  theme_minimal(base_size = base_size, base_family = "sans") +
    theme(
      text = element_text(color = pequi_dark),
      plot.title = element_text(face = "bold", size = base_size + 1, hjust = 0),
      plot.subtitle = element_text(size = base_size - 1, margin = margin(b = 7)),
      axis.title = element_text(face = "bold", size = base_size - 1),
      axis.text = element_text(size = base_size - 1, color = pequi_dark),
      panel.grid.minor = element_blank(),
      panel.grid.major.y = element_blank(),
      panel.grid.major.x = element_line(color = pequi_gray, linewidth = 0.25),
      plot.background = element_rect(fill = "white", color = NA),
      panel.background = element_rect(fill = "white", color = NA),
      legend.position = "bottom",
      legend.title = element_blank(),
      legend.text = element_text(size = base_size - 1),
      plot.margin = margin(6, 12, 6, 6)
    )
}

panel_design <- ggplot(strata, aes(x = configuracoes, y = estrato)) +
  geom_col(width = 0.54, fill = pequi_green, color = pequi_dark, linewidth = 0.25) +
  geom_text(
    aes(x = rotulo_x, label = rotulo, hjust = rotulo_hjust, color = rotulo_cor),
    size = 3.0,
    show.legend = FALSE
  ) +
  scale_color_identity() +
  scale_x_continuous(
    limits = c(0, 64),
    breaks = c(0, 14, 28, 42, 56),
    expand = c(0, 0)
  ) +
  labs(
    title = "A. Desenho pareado",
    subtitle = "Unidade Wilcoxon: cenário + semente",
    x = "Configurações do plano fatorial",
    y = NULL
  ) +
  annotate(
    "label",
    x = 0,
    y = 0.45,
    hjust = 0,
    vjust = 0,
    label = "Carga baixa = controle operacional\nH1 = média e alta congestão",
    size = 2.65,
    color = pequi_dark,
    fill = pequi_light,
    label.size = 0.15
  ) +
  theme_pequi()

panel_power <- ggplot(power_points, aes(x = efeito, y = poder, color = estrato, shape = estrato)) +
  annotate("rect", xmin = 0, xmax = 16, ymin = 0.80, ymax = 1.02, fill = pequi_light, alpha = 0.65) +
  geom_hline(yintercept = 0.80, color = pequi_dark, linewidth = 0.35, linetype = "dashed") +
  geom_vline(xintercept = 15, color = pequi_dark, linewidth = 0.35, linetype = "dashed") +
  geom_line(aes(linetype = estrato), linewidth = 0.85) +
  geom_point(size = 2.35, stroke = 0.75, fill = "white") +
  annotate("text", x = 15, y = 0.505, label = "H1 = 15%", angle = 90, hjust = 0, vjust = -0.45, size = 2.65, color = pequi_dark) +
  annotate("text", x = 0.15, y = 0.815, label = "poder 0,80", hjust = 0, vjust = -0.35, size = 2.65, color = pequi_dark) +
  annotate("label", x = medium_mde, y = 0.69, label = paste0("MDE média\n", comma_number(medium_mde, 1), "%"), size = 2.55, fill = "white", color = pequi_dark, label.size = 0.15) +
  annotate("label", x = high_mde, y = 0.90, label = paste0("MDE alta\n", comma_number(high_mde, 1), "%"), size = 2.55, fill = "white", color = pequi_dark, label.size = 0.15) +
  scale_color_manual(values = c("Média congestão" = pequi_green, "Alta congestão" = pequi_leaf)) +
  scale_shape_manual(values = c("Média congestão" = 16, "Alta congestão" = 15)) +
  scale_linetype_manual(values = c("Média congestão" = "solid", "Alta congestão" = "longdash")) +
  scale_x_continuous(
    limits = c(0, 16),
    breaks = c(0, 5, 10, 15),
    labels = function(x) comma_number(x, 0)
  ) +
  scale_y_continuous(
    limits = c(0.48, 1.03),
    breaks = c(0.50, 0.80, 1.00),
    labels = function(x) comma_number(x, 2)
  ) +
  labs(
    title = "B. Poder por bootstrap RHFS",
    subtitle = paste0(
      "Wilcoxon unilateral; ",
      integer_pt(bootstrap_replicates),
      " reamostragens; α = ",
      comma_number(alpha_value, 2)
    ),
    x = "Efeito imposto no p95 (%)",
    y = "Poder estimado"
  ) +
  theme_pequi()

open_device <- function(path) {
  if (capabilities("cairo")) {
    grDevices::cairo_pdf(path, width = 7.45, height = 4.05, family = "sans", onefile = FALSE)
  } else {
    grDevices::pdf(path, width = 7.45, height = 4.05, family = "sans", useDingbats = FALSE)
  }
}

open_device(tmp_output_path)
grid.newpage()
pushViewport(viewport(layout = grid.layout(1, 2, widths = unit(c(0.48, 0.52), "npc"))))
print(panel_design, vp = viewport(layout.pos.row = 1, layout.pos.col = 1))
print(panel_power, vp = viewport(layout.pos.row = 1, layout.pos.col = 2))
dev.off()

gs <- Sys.which("gs")
if (nzchar(gs)) {
  status <- system2(
    gs,
    c(
      "-q",
      "-dNOPAUSE",
      "-dBATCH",
      "-sDEVICE=pdfwrite",
      "-dCompatibilityLevel=1.5",
      "-dPDFSETTINGS=/prepress",
      paste0("-sOutputFile=", output_path),
      tmp_output_path
    )
  )
  if (!identical(status, 0L)) {
    stop("Falha ao converter a figura para PDF 1.5 via Ghostscript.")
  }
} else {
  warning("Ghostscript não encontrado; mantendo a versão PDF emitida pelo dispositivo R.")
  file.copy(tmp_output_path, output_path, overwrite = TRUE)
}
unlink(tmp_output_path)

message("Figura gerada em: ", output_path)
