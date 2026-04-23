# MarKIntel

A minimal market intelligence app built with Streamlit, Google News RSS, and local Ollama.
(NLP-based market intelligence app using Streamlit + Ollama)

## What it does
- Takes a company name/any thing you want to research about.
- Fetches recent headlines
- Sends them to Ollama
- Shows sentiment, keywords, risks, opportunities, and a short AI summary

##Topics
nlp
streamlit
ollama
machine-learning
ai

## Requirements
- Python 3.10+
- Ollama running locally
- At least one Ollama model installed
- Please install requirements.txt file 
- If Ollama not installed please install it.
- Download Llama 3.2:3B model using ollama pull llama3.2:3b

## Run
```powershell
pip install -r requirements.txt
streamlit run app.py
```

## Optional environment variables
- `OLLAMA_HOST` (default: `http://localhost:11434`)
- `OLLAMA_MODEL` (preferred model name)

## Notes
This app uses Google News RSS for the headline source and local Ollama for the summary layer.
