# Consegna dopo l’audit

Questo documento descrive il controllo precedente. La presentazione aggiornata, il confronto a parità di ritardo e il test A/B sono nel [README attuale](../README.it.md). I modelli esistenti restano invariati; il progetto finale ha 24 test superati.

**Condivisibile con limiti espliciti.** Ho affrontato tutte le sette richieste e applicato le correzioni. La revisione è parziale solo per la verifica esaustiva delle interazioni del browser. I totali indicano gli elementi del perimetro, non una certificazione di ogni stato possibile.

## Risultati e correzioni verificate

1. Mancava lo storico di categoria; la disponibilità degli snapshot non era dimostrata. **Corretto:** storico di categoria, test di acquisti/consegne precedenti e tutte le 19 variabili documentate. Il lift temporale passa da 2,87x a 2,59x.

2. Il beneficio di riacquisto era ipotizzato senza una coorte misurata. **Corretto:** customer_unique_id, coorte matura a 90 giorni 754/72.373 riacquisti, aumento base zero e conteggio unico per acquirente.

3. Usavo la risposta invece della creazione del questionario; errori raggruppati non equivalevano a effetti fissi. **Corretto:**81,63% di creazioni prima della consegna tra i ritardi, sensibilità per giorno 72,74%, modelli prima/dopo ed effetti fissi. Differenza grezza -2,031 contro primo giorno aggiustato -0,800; associazioni non causali.

4. Selezione del testo e attribuzione delle recensioni condivise erano incomplete. **Corretto:**57,63% senza testo, distribuzioni dei voti, temi solo con testo, una recensione per ordine ed effetti fissi/ranking a venditore singolo.

5. Lo scenario a ritardo zero ricostruiva i termini dalla durata originale. **Corretto:** azzeramento completo e test. Incremento finale +0,0066 a +0,0165 stelle; netto base -R$52.817, pareggio R$0,1231/ordine.

6. Mancavano esclusioni per i binari. **Corretto:** dati grezzi, modelli, Parquet e vettori esclusi, verificati con git check-ignore in un repository temporaneo isolato. Script Kaggle/checksum e attribuzione CC BY-NC-SA 4.0 bilingue verificati. Il progetto non ha metadati Git.

## Qualità della demo

| Categoria | Difetti osservati | Valutazione |
| --- | --- | --- |
| Utilità e completezza della demo | 0 / 7 | Tutte le sette domande affrontate. Calibrazione attuale e responsabilità causale richiedono nuovi dati. |
| Chiarezza analitica | 0 / 7 | Tutti i confronti richiesti presenti; soglia e pendenza separate. |
| Coerenza visiva e interazioni | 0 / 9 | Grafici e panoramiche nelle due lingue ispezionati; moduli e scenari testati. Non verificate esaustivamente tutte le combinazioni dei filtri nel browser. |

## Correttezza analitica

| Categoria | Difetti osservati | Valutazione |
| --- | --- | --- |
| Autorità e affidabilità delle fonti | 0 / 7 | Fonte e licenza ufficiali verificate. Versioni storiche di catalogo/promessa non disponibili: disponibilità al checkout ipotizzata. |
| Accuratezza dei valori | 0 / 6 | Conteggi grezzi, equivalenza degli effetti fissi, identità dei riacquisti, formule e test temporale riconciliati. |
| Coerenza interna dei grafici | 0 / 8 | Grafici verificati nelle due lingue; titoli, legende e intervalli coerenti con le nuove tabelle. |
| Dettagli delle fonti | 0 / 8 | Note dei grafici indicano popolazione, periodo e metodo; fonte e denominatori completi nei README collegati. |
| Coerenza tra gli artefatti | 0 / 9 | README, riepilogo, demo, immagini e notebook eseguiti riflettono la nuova analisi. |
| Controlli di qualità dei dati | 0 / 7 | Verificati confini temporali, sensibilità alla mezzanotte, testo mancante, più venditori e osservazione matura. |
| Supporto delle conclusioni | 0 / 6 | Conclusioni limitate ad associazioni e scenari ipotizzati; nessun risparmio realizzato dichiarato. |

[Rapporto completo](../README.it.md). 20 test superati; entrambi i notebook eseguiti senza errori.
