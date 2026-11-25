---
title: Will this tender end up void?
emoji: 📄
colorFrom: blue
colorTo: gray
sdk: static
app_file: index.html
pinned: false
short_description: Risk that a Chilean public tender ends void
---

# ¿Quedará desierta esta licitación?

Estimates, at publication time, the probability that a Chilean public tender (Mercado Público) ends up void, and shows the three factors that weighed most.

- **Model:** LightGBM trained on tenders published April–June 2026, temporal split. On unseen data, the 10% of tenders flagged as riskiest ended void 40% of the time — twice the base rate.
- **Runs in your browser:** the LightGBM model is exported to JSON and evaluated client-side (a parity test checks it matches the Python model), so nothing you type is sent to a server. The FastAPI version, with interactive docs, runs from the repository's Docker image.
- **Code, methodology and monitoring:** [github.com/CarlosIgRuz/compras-publicas-cl](https://github.com/CarlosIgRuz/compras-publicas-cl)

This Space is deployed automatically from the GitHub repository.

*Fuente de los datos: Dirección ChileCompra.*
