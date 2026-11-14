import os
import requests
import pandas as pd
import yfinance as yf
from ta.trend import EMAIndicator
from ta.momentum import RSIIndicator
from ta.volatility import AverageTrueRange

TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
SYMBOL = "GC=F"
INTERVAL = "15m"
RR = 2.0


def envoyer(texte):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    r = requests.post(url, data={"chat_id": CHAT_ID, "text": texte})
    print("Telegram :", r.status_code)


def donnees():
    df = yf.download(SYMBOL, period="5d", interval=INTERVAL, progress=False)
    df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
    return df.dropna()


def analyser(df):
    close = df["Close"]
    df["ema50"] = EMAIndicator(close, 50).ema_indicator()
    df["ema200"] = EMAIndicator(close, 200).ema_indicator()
    df["rsi"] = RSIIndicator(close, 14).rsi()
    df["atr"] = AverageTrueRange(df["High"], df["Low"], close, 14).average_true_range()
    d = df.iloc[-1]
    atr = float(d["atr"])
    ema50, ema200, rsi = float(d["ema50"]), float(d["ema200"]), float(d["rsi"])

    if ema50 > ema200 and rsi < 45:
        entree = round(ema50, 2)
        sl = round(entree - 1.5 * atr, 2)
        tp = round(entree + RR * (entree - sl), 2)
        return ("Buy Limit", entree, sl, tp)

    if ema50 < ema200 and rsi > 55:
        entree = round(ema50, 2)
        sl = round(entree + 1.5 * atr, 2)
        tp = round(entree - RR * (sl - entree), 2)
        return ("Sell Limit", entree, sl, tp)
    return None


def message(sig):
    genre, entree, sl, tp = sig
    return (
        f"SIGNAL OR (XAUUSD) : {genre}\n"
        f"Entree : {entree}\nStop loss : {sl}\nTake profit : {tp}\n"
        "Ratio 1 pour 2\n\n"
        "Dans MetaTrader 5 :\n"
        "1. Onglet Trade, bouton +\n"
        "2. Symbole XAUUSD\n"
        f"3. Type : Ordre en attente, {genre}\n"
        "4. Entre le prix d'entree, le stop loss et le take profit\n"
        "5. Volume petit : risque 1% du capital\n"
        "6. Appuie sur Placer\n\n"
        "Verifie le prix dans MT5 avant de valider."
    )


if __name__ == "__main__":
    if os.environ.get("TEST_MESSAGE") == "true":
        envoyer("Test OK : ton bot Telegram fonctionne.")
    else:
        sig = analyser(donnees())
        if sig:
            envoyer(message(sig))
            print("Signal envoye", sig)
        else:
            print("Pas de signal")
