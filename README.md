# Care Finder India

Care Finder India is a Streamlit application for finding healthcare facilities in India based on a requested service and location. It uses recorded information from the Virtue Foundation healthcare facilities dataset and explains why a facility appears in the results.

## What the application does

- Searches for dialysis, NICU, MRI, trauma care, burn care, general emergency care, and emergency C-sections.
- Lets users search by an available city/state, and supports additional location options where configured.
- Looks for service-specific statements in facility records and distinguishes stronger matches from weak or conflicting wording.
- Checks for some inconsistent coordinates, duplicate claims, and statements that may refer to another facility or branch.
- Shows nearby matches on a map, compares facilities, and displays recorded contact details and source links.
- Handles emergency C-section results cautiously: separate mentions of C-section and 24-hour emergency care are shown as **leads to verify**, not confirmation of emergency surgical readiness.

Results use a **dataset match score**, not a clinical quality, safety, or live availability rating. Distances are straight-line estimates rather than driving times.

## Technology

Python, Streamlit, pandas, PyDeck, Databricks SQL Connector, Databricks SDK, and Unity Catalog. The development notebook also contains exploratory PySpark, regex matching, and NLP evaluation experiments. Those experiments are not the live ranking method used by the app.

## Files

| File | Purpose |
| --- | --- |
| `app.py` | Streamlit application and search/ranking logic |
| `app.yaml` | Databricks Apps startup command and resource bindings |
| `requirements.txt` | Dependencies for the deployed Streamlit app |
| `Care_Finder_India_Final_Submission.ipynb` | Combined exploration, audits, experiments, saved-metrics recheck, and app source |
| `data/*.csv` | Five supplied Phase 4 and Phase 5 review, validation, and prediction files |

## Running the application in Databricks

1. Make the processed Unity Catalog table available to your Databricks App. The default table name expected by `app.py` is `workspace.default.care_finder_facilities`.
2. Configure Databricks Apps resources matching `app.yaml`: a SQL warehouse resource with the key `sql-warehouse`, and a table resource with the key `table`. Ensure the app identity has permissions to use the warehouse and read the table.
3. Deploy `app.py`, `app.yaml`, and `requirements.txt` as the Databricks App source. The app starts with `streamlit run app.py`.
4. The app reads `DATABRICKS_WAREHOUSE_ID` and `UC_TABLE_NAME` from its environment. An optional `GEOAPIFY_API_KEY` enables additional geocoding-based location searches. Provide keys using secure app configuration; **do not commit secrets**.

The hosted app depends on Databricks access and is not a standalone offline directory. Opening the public repository does not grant access to its Unity Catalog data.

## Notebook data and execution notes

The consolidated notebook includes a **self-contained evaluation section near the top**. To rerun the supplied Phase 4 regex evaluation and Phase 5 saved NLI/hybrid metrics:

1. Download or clone the repository, keeping the notebook and the `data/` folder in the same directory.
2. Install Python and pandas (for example, `pip install pandas notebook`), then open `Care_Finder_India_Final_Submission.ipynb` in Jupyter or VS Code.
3. Run the **"Run the saved evaluation results without Databricks"** section near the start. It reads only local CSVs, and needs no Databricks connection or model downloads.
4. If the CSVs live elsewhere, set the environment variable `CARE_FINDER_DATA_DIR` to their directory before running the setup cell.

These are **recalculations using saved scores and reference labels**, not new model inference or independent confirmation of healthcare services. The Phase 5 labels were drafted with AI assistance and **all 140 labels were subsequently manually reviewed by a team member**. This is human review of text-evidence classifications, **not independent clinical verification** of hospital capabilities. The evaluation metrics are therefore exploratory text-classification results, not clinically validated accuracy measures. The Phase 5 validation CSV is an *unlabeled* sample; its `gold_label` column is intentionally empty. Use `care_finder_phase5_provisional_labeled.csv` for the AI-assisted, human-reviewed annotations or `care_finder_phase5_predictions.csv` for the stored method predictions.

### Full Databricks analysis

The earlier notebook phases were developed separately and are **not designed to execute from first to last as one uninterrupted session**. They rely on Databricks PySpark, variables from their own phases, and sometimes extra experimental libraries. To rerun facility exploration, sampling, or model inference, use an authorized Databricks workspace with access to:

- Original source table: `databricks_virtue_foundation_dataset_dais_2026.virtue_foundation_dataset.facilities`
- Processed application table: `workspace.default.care_finder_facilities`
- Databricks permissions and any experimental dependencies (`pyspark`, `scikit-learn`, `transformers`, `sentence-transformers`, etc.)

The `data/` files supplied here are **evaluation artifacts**, not a replacement for the full facility dataset or the processed Unity Catalog table. Randomly regenerating the review sample may produce different facility statements; saved labels must not be joined to a newly sampled set by `review_id` alone.

### Included evaluation files

| File | Description |
| --- | --- |
| `data/care_finder_phase4_provisional_labels.csv` | 84 review IDs with associated labels and notes |
| `data/care_finder_phase4_review_labeled.csv` | 84 original reviewed claims with regex baseline and labels |
| `data/care_finder_phase5_validation.csv` | 140 sampled claims, with labels still blank |
| `data/care_finder_phase5_provisional_labeled.csv` | 140 claims with AI-assisted, manually reviewed labels and notes |
| `data/care_finder_phase5_predictions.csv` | Same 140 human-reviewed text labels with saved NLI and hybrid predictions |

Only publish these evaluation artifacts if their redistribution is permitted under the datathon's data-use terms.

## Limitations

The provided dataset is a record of facility information, not proof of current staffing, beds, equipment functionality, surgical readiness, or willingness to accept a patient. Statements may be incomplete, outdated, misattributed, or geographically inconsistent. Care Finder attempts to make those uncertainties clearer but does not independently verify them. In an emergency, use local emergency services rather than relying on the directory.

## Project status

Datathon prototype. The app's rule-based matching and location checks were developed for explainable facility discovery; experimental notebook classification scores do not represent clinical performance or guarantee of service availability.
