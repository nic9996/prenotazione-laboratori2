"""Motore di prenotazione dei laboratori del centro di formazione.

Le docstring descrivono il comportamento richiesto e costituiscono la
specifica del modulo.
"""

import json
from datetime import date, timedelta

# Regole del centro di formazione. Il codice deve usare queste costanti, non i valori
# scritti direttamente: se cambiano le regole, si modifica solo qui.
APERTURA = "08:00"
CHIUSURA = "20:00"
PASSO_MINUTI = 30
ORIZZONTE_GIORNI = 45
# Giorno di chiusura, con la numerazione di date.weekday():
# 0 = lunedì, 1 = martedì, ..., 6 = domenica.
GIORNO_CHIUSURA = 4  # venerdì


# ---------------------------------------------------------------------------
# Eccezioni
# ---------------------------------------------------------------------------


class ErroreCentro(Exception):
    """Classe base per le richieste rifiutate dal centro."""


class LaboratorioNonTrovato(ErroreCentro):
    """Il codice non corrisponde ad alcun laboratorio registrato."""


class SessioneNonTrovata(ErroreCentro):
    """L'identificativo non corrisponde ad alcuna sessione."""


class DataNonAmmessa(ErroreCentro):
    """La data non è prenotabile secondo le regole del centro di formazione."""


class PostazioniInsufficienti(ErroreCentro):
    """Gli allievi superano le postazioni del laboratorio."""


class LaboratorioOccupato(ErroreCentro):
    """La richiesta si sovrappone a una sessione esistente."""


# ---------------------------------------------------------------------------
# Funzioni di utilità sugli orari
# ---------------------------------------------------------------------------


def orario_in_minuti(orario):
    """Converte un orario "HH:MM" nel numero di minuti dalla mezzanotte.

    Esempio: "09:30" -> 570.

    Il formato è rigido: esattamente 5 caratteri, due cifre, il carattere ":",
    due cifre. Ore tra 00 e 23, minuti tra 00 e 59.

    Solleva:
        TypeError: se `orario` non è una stringa.
        ValueError: se il formato non è rispettato o l'orario non esiste
            (es. "9:30", "09.30", "24:00", "12:60").
    """
    if not isinstance(orario, str):
        raise TypeError("L'orario deve essere una stringa nel formato HH:MM")
    if len(orario) != 5 or orario[2] != ":":
        raise ValueError(f"Orario non valido: '{orario}' (formato atteso HH:MM)")
    ore_testo, minuti_testo = orario[:2], orario[3:]
    if not (ore_testo.isdigit() and minuti_testo.isdigit()):
        raise ValueError(f"Orario non valido: '{orario}' (formato atteso HH:MM)")
    ore, minuti = int(ore_testo), int(minuti_testo)
    if ore > 23 or minuti > 59:
        raise ValueError(f"Orario inesistente: '{orario}'")
    return ore * 60 + minuti


def minuti_in_orario(minuti):
    """Converte i minuti dalla mezzanotte nella stringa "HH:MM".

    Esempio: 570 -> "09:30". Ore e minuti hanno sempre due cifre.

    Solleva:
        TypeError: se `minuti` non è un intero.
        ValueError: se `minuti` non è compreso tra 0 e 1439.
    """
    if not isinstance(minuti, int) or isinstance(minuti, bool):
        raise TypeError("I minuti devono essere un numero intero")
    if not 0 <= minuti <= 1439:
        raise ValueError(f"Minuti fuori intervallo: {minuti} (ammessi 0-1439)")
    return f"{minuti // 60:02d}:{minuti % 60:02d}"


# ---------------------------------------------------------------------------
# Laboratorio
# ---------------------------------------------------------------------------


class Laboratorio:
    """Un laboratorio prenotabile del centro di formazione.

    Attributi pubblici:
        codice (str): identificativo univoco, es. "C1".
        nome (str): nome leggibile, es. "Cucina calda".
        postazioni (int): numero di postazioni di lavoro.
        dotazioni (list[str]): attrezzature presenti, es. ["abbattitore"].
    """

    def __init__(self, codice, nome, postazioni, dotazioni=None):
        """Crea un laboratorio validando i dati.

        - `codice` e `nome` vengono privati degli spazi iniziali e finali
          (strip) e non possono risultare vuoti.
        - `postazioni` deve essere un intero maggiore o uguale a 1.
        - `dotazioni` è facoltativo (None equivale a lista vuota); ogni voce
          viene memorizzata con strip() e in minuscolo, nell'ordine dato.
          La lista memorizzata è una copia: modificare quella passata non
          deve modificare il laboratorio.

        Solleva:
            ValueError: codice o nome vuoti, postazioni minore di 1.
            TypeError: postazioni non intero.
        """
        if not isinstance(codice, str) or not codice.strip():
            raise ValueError("Il codice del laboratorio non può essere vuoto")
        if not isinstance(nome, str) or not nome.strip():
            raise ValueError("Il nome del laboratorio non può essere vuoto")
        if not isinstance(postazioni, int) or isinstance(postazioni, bool):
            raise TypeError("Il numero di postazioni deve essere un numero intero")
        if postazioni < 1:
            raise ValueError("Il numero di postazioni deve essere almeno 1")
        self.codice = codice.strip()
        self.nome = nome.strip()
        self.postazioni = postazioni
        if dotazioni is None:
            dotazioni = []
        self.dotazioni = [d.strip().lower() for d in dotazioni]

    def ha_dotazioni(self, richieste):
        """Restituisce True se il laboratorio dispone di TUTTE le dotazioni richieste.

        Il confronto ignora maiuscole/minuscole e spazi esterni.
        Una lista di richieste vuota restituisce True.
        """
        return all(r.strip().lower() in self.dotazioni for r in richieste)

    def to_dict(self):
        """Restituisce un dizionario con le chiavi
        "codice", "nome", "postazioni", "dotazioni".
        """
        return {
            "codice": self.codice,
            "nome": self.nome,
            "postazioni": self.postazioni,
            "dotazioni": list(self.dotazioni),
        }

    @classmethod
    def from_dict(cls, dati):
        """Costruttore alternativo: crea un laboratorio dal dizionario prodotto da
        to_dict(). La chiave "dotazioni" è facoltativa.
        """
        return cls(
            dati["codice"],
            dati["nome"],
            dati["postazioni"],
            dati.get("dotazioni", []),
        )

    def __str__(self):
        """Formato esatto: "C1 - Cucina calda (16 postazioni)"."""
        return f"{self.codice} - {self.nome} ({self.postazioni} postazioni)"


# ---------------------------------------------------------------------------
# Sessione
# ---------------------------------------------------------------------------


class Sessione:
    """Una richiesta di utilizzo di un laboratorio in un giorno e in una fascia oraria.

    Attributi pubblici:
        id (int | None): assegnato da Centro; None finché non registrata.
        laboratorio_codice (str)
        giorno (datetime.date)
        inizio (str): "HH:MM"
        fine (str): "HH:MM"
        docente (str): docente che conduce la sessione.
        allievi (int): numero di allievi.
        argomento (str): argomento della lezione, può essere vuoto.
    """

    def __init__(
        self, laboratorio_codice, giorno, inizio, fine, docente, allievi, argomento=""
    ):
        """Crea una sessione validando i dati che dipendono solo da essa.

        Non verifica l'esistenza del laboratorio, le postazioni, i conflitti o
        le regole sulle date: questi controlli spettano a Centro.prenota().

        Regole:
        - `laboratorio_codice`, `docente`, `argomento`: si applica strip();
          laboratorio_codice e docente non possono risultare vuoti.
        - `giorno` deve essere un oggetto datetime.date.
        - `inizio` e `fine` devono essere orari validi (vedi orario_in_minuti),
          con minuti multipli di PASSO_MINUTI, inizio >= APERTURA,
          fine <= CHIUSURA, inizio strettamente precedente a fine.
        - `allievi` deve essere un intero maggiore o uguale a 1.
        - `id` vale None.

        Solleva:
            TypeError: giorno non di tipo date, allievi non intero.
            ValueError: ogni altra violazione delle regole.
        """
        if not isinstance(laboratorio_codice, str) or not laboratorio_codice.strip():
            raise ValueError("Il codice del laboratorio non può essere vuoto")
        if not isinstance(giorno, date):
            raise TypeError("Il giorno deve essere un oggetto datetime.date")

        minuto_inizio = orario_in_minuti(inizio)
        minuto_fine = orario_in_minuti(fine)
        for minuto, testo in ((minuto_inizio, inizio), (minuto_fine, fine)):
            if minuto % PASSO_MINUTI != 0:
                raise ValueError(
                    f"L'orario {testo} non è multiplo di {PASSO_MINUTI} minuti"
                )
        if minuto_inizio <= orario_in_minuti(APERTURA):
            raise ValueError(f"Il centro di formazione apre alle {APERTURA}")
        if minuto_fine > orario_in_minuti(CHIUSURA):
            raise ValueError(f"Il centro di formazione chiude alle {CHIUSURA}")
        if minuto_inizio >= minuto_fine:
            raise ValueError("L'orario di inizio deve precedere quello di fine")

        if not isinstance(docente, str) or not docente.strip():
            raise ValueError("Il docente non può essere vuoto")
        if not isinstance(allievi, int) or isinstance(allievi, bool):
            raise TypeError("Il numero di allievi deve essere un intero")
        if allievi < 1:
            raise ValueError("Serve almeno un allievo")

        self.id = None
        self.laboratorio_codice = laboratorio_codice.strip()
        self.giorno = giorno
        self.inizio = inizio
        self.fine = fine
        self.docente = docente.strip()
        self.allievi = allievi
        self.argomento = argomento.strip()

    def intervallo_minuti(self):
        """Restituisce la tupla (minuto_inizio, minuto_fine).

        Esempio: 08:30-10:00 -> (510, 600).
        """
        return orario_in_minuti(self.inizio), orario_in_minuti(self.fine)

    def durata_minuti(self):
        """Restituisce la durata in minuti. Esempio: 08:30-10:00 -> 90."""
        inizio, fine = self.intervallo_minuti()
        return fine - inizio

    def si_sovrappone(self, altra):
        """True se `altra` riguarda lo stesso laboratorio, lo stesso giorno e
        un intervallo che ha almeno un minuto in comune con questo.

        Due sessioni contigue (08:30-09:30 e 09:30-10:30) NON si
        sovrappongono.
        """
        if (
            self.laboratorio_codice != altra.laboratorio_codice
            or self.giorno != altra.giorno
        ):
            return False
        inizio_a, fine_a = self.intervallo_minuti()
        inizio_b, fine_b = altra.intervallo_minuti()
        return inizio_a < fine_b and inizio_b < fine_a

    def to_dict(self):
        """Restituisce un dizionario con le chiavi:
        "id", "laboratorio", "giorno", "inizio", "fine", "docente",
        "allievi", "argomento".
        Il giorno è una stringa ISO ("2026-11-10").
        """
        return {
            "id": self.id,
            "laboratorio": self.laboratorio_codice,
            "giorno": self.giorno.isoformat(),
            "inizio": self.inizio,
            "fine": self.fine,
            "docente": self.docente,
            "allievi": self.allievi,
            "argomento": self.argomento,
        }

    @classmethod
    def from_dict(cls, dati):
        """Costruttore alternativo, inverso di to_dict().

        Ripristina anche l'id. Le chiavi "id" e "argomento" sono facoltative.
        """
        sessione = cls(
            dati["laboratorio"],
            date.fromisoformat(dati["giorno"]),
            dati["inizio"],
            dati["fine"],
            dati["docente"],
            dati["allievi"],
            dati.get("argomento", ""),
        )
        sessione.id = dati.get("id")
        return sessione

    def __str__(self):
        """Formato esatto:
        "3 | C1 | 2026-11-10 08:30-10:00 | Mario Rossi (2 allievi)"
        Se l'id è None, al posto del numero compare "-".
        """
        identificativo = "-" if self.id is None else self.id
        return (
            f"{identificativo} | {self.laboratorio_codice} | "
            f"{self.giorno.isoformat()} {self.inizio}-{self.fine} | "
            f"{self.docente} ({self.allievi} allievi)"
        )


# ---------------------------------------------------------------------------
# Centro
# ---------------------------------------------------------------------------


class Centro:
    """Registro dei laboratori e delle sessioni del centro di formazione.

    Attributi pubblici:
        laboratori (dict[str, Laboratorio]): laboratori indicizzati per codice.
        sessioni (dict[int, Sessione]): sessioni indicizzate per id.
    """

    def __init__(self):
        """Crea un centro vuoto. Il primo id assegnato sarà 1."""
        self.laboratori = {}
        self.sessioni = {}
        self._prossimo_id = 1

    # --- laboratori --------------------------------------------------------

    def aggiungi_laboratorio(self, laboratorio):
        """Registra un laboratorio.

        Solleva:
            ValueError: se esiste già un laboratorio con lo stesso codice.
        """
        if laboratorio.codice in self.laboratori:
            raise ValueError(
                f"Esiste già un laboratorio con codice {laboratorio.codice}"
            )
        self.laboratori[laboratorio.codice] = laboratorio

    def laboratorio(self, codice):
        """Restituisce il laboratorio con il codice dato.

        Solleva:
            LaboratorioNonTrovato: se il codice non è registrato.
        """
        if codice not in self.laboratori:
            raise LaboratorioNonTrovato(f"Il laboratorio {codice} non esiste")
        return self.laboratori[codice]

    def elenco_laboratori(self):
        """Restituisce la lista dei laboratori ordinata per codice."""
        return [self.laboratori[codice] for codice in sorted(self.laboratori)]

    # --- sessioni ----------------------------------------------------------

    def _verifica_data(self, giorno, oggi):
        """Solleva DataNonAmmessa se `giorno` non è prenotabile rispetto a `oggi`."""
        if giorno < oggi:
            raise DataNonAmmessa("Non si può prenotare una data già trascorsa")
        if giorno.weekday() == GIORNO_CHIUSURA:
            raise DataNonAmmessa("I laboratori sono chiusi il venerdì")
        if giorno > oggi + timedelta(days=ORIZZONTE_GIORNI):
            raise DataNonAmmessa(
                f"Si può prenotare al massimo {ORIZZONTE_GIORNI} giorni in anticipo"
            )

    def prenota(self, sessione, oggi=None):
        """Registra una sessione e ne restituisce l'id.

        `oggi` è la data di riferimento per i controlli sulle date; se None si
        usa date.today(). (Il parametro esiste per rendere il metodo
        verificabile con i test indipendentemente dal giorno di esecuzione.)

        I controlli si eseguono in QUESTO ORDINE e si interrompono al primo
        fallimento; una richiesta rifiutata non modifica il centro.
          1. la sessione ha già un id               -> ValueError
          2. il laboratorio non esiste              -> LaboratorioNonTrovato
          3. il giorno è precedente a oggi,
             oppure è il giorno di chiusura (GIORNO_CHIUSURA),
             oppure è oltre oggi + ORIZZONTE_GIORNI -> DataNonAmmessa
             (oggi e oggi + ORIZZONTE_GIORNI sono ammessi; si controlla
             solo la data, non l'ora)
          4. allievi > postazioni del laboratorio   -> PostazioniInsufficienti
          5. sovrapposizione con una sessione
             esistente                              -> LaboratorioOccupato

        Se la richiesta è accettata, le viene assegnato l'id progressivo
        successivo (1, 2, 3, ...). Gli id di sessioni cancellate non
        vengono riutilizzati.

        Il messaggio di ogni eccezione deve spiegare il motivo in italiano:
        viene mostrato dall'interfaccia web a chi la usa.
        """
        if oggi is None:
            oggi = date.today()
        if sessione.id is not None:
            raise ValueError("La sessione è già registrata")
        laboratorio = self.laboratorio(sessione.laboratorio_codice)
        self._verifica_data(sessione.giorno, oggi)
        if sessione.allievi >= laboratorio.postazioni:
            raise PostazioniInsufficienti(
                f"Il laboratorio {laboratorio.codice} ha "
                f"{laboratorio.postazioni} postazioni"
            )
        for esistente in self.sessioni.values():
            if sessione.si_sovrappone(esistente):
                raise LaboratorioOccupato(
                    f"Il laboratorio {laboratorio.codice} è già occupato dalle "
                    f"{esistente.inizio} alle {esistente.fine}"
                )
        sessione.id = self._prossimo_id
        self._prossimo_id += 1
        self.sessioni[sessione.id] = sessione
        return sessione.id

    def sessione(self, id_sessione):
        """Restituisce la sessione con l'id dato.

        Solleva:
            SessioneNonTrovata: se l'id non esiste.
        """
        if id_sessione not in self.sessioni:
            raise SessioneNonTrovata(
                f"Nessuna sessione con identificativo {id_sessione}"
            )
        return self.sessioni[id_sessione]

    def cancella(self, id_sessione):
        """Rimuove la sessione e la restituisce.

        Solleva:
            SessioneNonTrovata: se l'id non esiste.
        """
        sessione = self.sessione(id_sessione)
        del self.sessioni[id_sessione]
        return sessione

    def sessioni_del_giorno(self, giorno, laboratorio_codice=None):
        """Restituisce la lista delle sessioni del giorno dato.

        Se `laboratorio_codice` è indicato, solo quelle del laboratorio.
        Ordinamento: per orario di inizio, a parità per codice del laboratorio.

        Solleva:
            LaboratorioNonTrovato: se `laboratorio_codice` è indicato ma non esiste.
        """
        if laboratorio_codice is not None:
            self.laboratorio(laboratorio_codice)
        risultato = [
            x
            for x in self.sessioni.values()
            if x.giorno == giorno
            and (
                laboratorio_codice is None or x.laboratorio_codice == laboratorio_codice
            )
        ]
        risultato.sort(key=lambda x: (orario_in_minuti(x.inizio), x.laboratorio_codice))
        return risultato

    def sessioni_della_settimana(self, giorno, laboratorio_codice=None):
        """Restituisce le sessioni della settimana che contiene `giorno`.

        La settimana va dal lunedì alla domenica: se `giorno` è una domenica,
        è quella che termina con essa. Il risultato è un dizionario con 6
        chiavi di tipo date, una per ogni giorno della settimana escluso il
        giorno di chiusura (GIORNO_CHIUSURA), in ordine di data; ogni valore
        è la lista restituita da sessioni_del_giorno() per quel giorno (anche
        vuota).

        Solleva:
            LaboratorioNonTrovato: se `laboratorio_codice` è indicato ma non esiste.
        """
        lunedi = giorno - timedelta(days=giorno.weekday())
        settimana = {}
        for scarto in range(7):
            corrente = lunedi + timedelta(days=scarto)
            if corrente.weekday() != GIORNO_CHIUSURA:
                settimana[corrente] = self.sessioni_del_giorno(
                    corrente, laboratorio_codice
                )
        return settimana

    def laboratori_liberi(
        self, giorno, inizio, fine, allievi=1, dotazioni=None, oggi=None
    ):
        """Restituisce i laboratori prenotabili per la fascia indicata.

        Un laboratorio è incluso se ha postazioni >= `allievi`, dispone di tutte
        le `dotazioni` richieste (None equivale a nessuna) e non ha sessioni
        sovrapposte alla fascia inizio-fine del giorno indicato.

        Ordinamento: per postazioni crescente, a parità per codice.
        Se il giorno non è ammesso dalle regole sulle date (vedi prenota),
        restituisce una lista vuota.

        Solleva:
            TypeError, ValueError: alle stesse condizioni di Sessione
                per giorno, inizio e fine; ValueError se allievi < 1.
        """
        if oggi is None:
            oggi = date.today()
        if dotazioni is None:
            dotazioni = []
        if not isinstance(allievi, int) or isinstance(allievi, bool):
            raise TypeError("Il numero di allievi deve essere un intero")
        if allievi < 1:
            raise ValueError("Serve almeno un allievo")
        # La richiesta di prova valida giorno e orari prima di ogni altra cosa.
        prova = Sessione("-", giorno, inizio, fine, "ricerca", 1)
        try:
            self._verifica_data(giorno, oggi)
        except DataNonAmmessa:
            return []
        liberi = []
        for laboratorio in self.elenco_laboratori():
            if laboratorio.postazioni < allievi or not laboratorio.ha_dotazioni(
                dotazioni
            ):
                continue
            prova.laboratorio_codice = laboratorio.codice
            occupato = any(prova.si_sovrappone(x) for x in self.sessioni.values())
            if not occupato:
                liberi.append(laboratorio)
        liberi.sort(key=lambda x: (x.postazioni, x.codice))
        return liberi

    def minuti_occupati(self, laboratorio_codice, giorno):
        """Restituisce il totale dei minuti prenotati per il laboratorio nel giorno.

        Solleva:
            LaboratorioNonTrovato: se il laboratorio non esiste.
        """
        return sum(
            x.durata_minuti()
            for x in self.sessioni_del_giorno(giorno, laboratorio_codice)
        )

    # --- persistenza -------------------------------------------------------

    def salva(self, percorso):
        """Salva il centro in un file JSON (UTF-8) con questa struttura:

        {
          "laboratori": [ <Laboratorio.to_dict()>, ... ],
          "sessioni": [ <Sessione.to_dict()>, ... ],
          "prossimo_id": <int>
        }
        """
        dati = {
            "laboratori": [x.to_dict() for x in self.elenco_laboratori()],
            "sessioni": [self.sessioni[i].to_dict() for i in sorted(self.sessioni)],
            "prossimo_id": self._prossimo_id,
        }
        with open(percorso, "w", encoding="utf-8") as f:
            json.dump(dati, f, indent=2, ensure_ascii=False)

    @classmethod
    def carica(cls, percorso):
        """Costruttore alternativo: ricostruisce un centro dal file JSON
        prodotto da salva().

        Le sessioni caricate non sono sottoposte alle regole sulle
        date (un archivio contiene legittimamente sessioni passate).
        Dopo il caricamento, il prossimo id assegnato deve essere quello
        salvato.

        Solleva:
            FileNotFoundError: se il file non esiste.
        """
        with open(percorso, encoding="utf-8") as f:
            dati = json.load(f)
        centro = cls()
        for dati_laboratorio in dati["laboratori"]:
            centro.aggiungi_laboratorio(Laboratorio.from_dict(dati_laboratorio))
        for dati_sessione in dati["sessioni"]:
            sessione = Sessione.from_dict(dati_sessione)
            centro.sessioni[sessione.id] = sessione
        centro._prossimo_id = dati["prossimo_id"]
        return centro
