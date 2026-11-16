import os
import json
from datetime import datetime, timedelta, timezone

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
COOLDOWN_HEURES = 4
FICHIER_ETAT = "state.json"


def envoyer(texte):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    r = requests.post(url, data={"chat_id": CHAT_ID, "text": texte})
    print("Telegram :", r.status_code)


def lire_etat():
    try:
        with open(FICHIER_ETAT) as f:
            return json.load(f)
    except Exception:
        return {}


def sauver_etat(etat):
    with open(FICHIER_ETAT, "w") as f:
        json.dump(etat, f)


def deja_envoye(etat, genre):
    dernier = etat.get(genre)
    if not dernier:
        return False
    t = datetime.fromisoformat(dernier)
    return datetime.now(timezone.utc) - t < timedelta(hours=COOLDOWN_HEURES)


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
    prix = float(d["Close"])
    atr = float(d["atr"])
    ema50, ema200, rsi = float(d["ema50"]), float(d["ema200"]), float(d["rsi"])

    # Tendance haussiere, prix au dessus de l'EMA50 : on attend un repli
    if ema50 > ema200 and rsi > 50 and prix > ema50 + 0.5 * atr:
        entree = round(ema50, 2)
        sl = round(entree - 1.5 * atr, 2)
        tp = round(entree + RR * (entree - sl), 2)
        if sl < entree < prix and tp > entree:
            return ("Buy Limit", entree, sl, tp, round(prix, 2))

    # Tendance baissiere, prix sous l'EMA50 : on attend un rebond
    if ema50 < ema200 and rsi < 50 and prix < ema50 - 0.5 * atr:
        entree = round(ema50, 2)
        sl = round(entree + 1.5 * atr, 2)
        tp = round(entree - RR * (sl - entree), 2)
        if prix < entree < sl and tp < entree:
            return ("Sell Limit", entree, sl, tp, round(prix, 2))
    return None


def message(sig):
    genre, entree, sl, tp, prix = sig
    return (
        f"SIGNAL OR (XAUUSD) : {genre}\n"
        f"Prix actuel (bot) : {prix}\n"
        f"Entree : {entree}\nStop loss : {sl}\nTake profit : {tp}\n"
        "Ratio 1 pour 2\n\n"
        "Dans MetaTrader 5 :\n"
        "1. Compare d'abord le prix actuel du XAUUSD avec celui ci dessus\n"
        "2. Onglet Trade, bouton +\n"
        "3. Symbole XAUUSD\n"
        f"4. Type : Ordre en attente, {genre}\n"
        "5. Entre le prix d'entree, le stop loss et le take profit\n"
        "6. Volume petit : risque 1% du capital\n"
        "7. Appuie sur Placer\n\n"
        "Si l'ordre n'est pas declenche dans 2 heures, supprime le."
    )


if __name__ == "__main__":
    if os.environ.get("TEST_MESSAGE") == "true":
        envoyer("Test OK : ton bot Telegram fonctionne.")
    else:
        sig = analyser(donnees())
        if not sig:
            print("Pas de signal")
        else:
            etat = lire_etat()
            if deja_envoye(etat, sig[0]):
                print("Signal deja envoye recemment", sig[0])
            else:
                envoyer(message(sig))
                etat[sig[0]] = datetime.now(timezone.utc).isoformat()
                sauver_etat(etat)
                print("Signal envoye", sig)
