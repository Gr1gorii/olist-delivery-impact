# Attribuzione e licenza dei dati

[English](DATA_LICENSE.md) | [Italiano](DATA_LICENSE.it.md)

Uso il [Brazilian E-Commerce Public Dataset by Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce), pubblicato da Olist su Kaggle. La fonte contiene ordini anonimizzati di un marketplace brasiliano dal 2016 al 2018.

Il dataset è pubblicato con licenza [Creative Commons Attribuzione-NonCommerciale-CondividiAlloStessoModo 4.0 Internazionale, CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/). Mantengo questa attribuzione, uso i dati per un’analisi didattica non commerciale e applico la stessa licenza agli adattamenti del dataset, inclusi i dati preparati, gli esempi di recensioni tradotti e i grafici basati sui dati. Questo avviso riguarda i dati e i loro adattamenti; non concede diritti aggiuntivi sui dati originali.

Aggrego gli articoli per ordine, mantengo la prima recensione compilata per ogni ordine, calcolo variabili di consegna e storico e traduco alcuni esempi di recensioni per la visualizzazione. I testi originali restano in portoghese. I rapporti descrivono i filtri e i calcoli utilizzati per ottenere i risultati.

Scarico le tabelle originali con:

```bash
python scripts/download_data.py --language it
```

Lo script salva i checksum SHA-256 in `data/manifest.json`. Escludo da Git le tabelle originali, i dataset Parquet preparati, i vettori degli embedding e i modelli binari tramite `.gitignore`. La consegna attuale è una cartella di progetto senza metadati Git; le esclusioni indicano il contenuto previsto di un repository futuro e non affermano che siano stati rimossi file già tracciati.

Prima di ridistribuire dati adattati, mantengo l’attribuzione e l’avviso di licenza, indico le mie modifiche e rispetto le condizioni di uso non commerciale e condivisione con la stessa licenza. Non suggerisco un’approvazione del progetto da parte di Olist.
