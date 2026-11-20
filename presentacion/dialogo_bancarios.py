import tkinter as tk
from tkinter import ttk

import pandas as pd

from presentacion.componentes import modal

FUENTE = ("Segoe UI", 10)
MARCADO, DESMARCADO = "☑", "☐"


def _moneda(valor):
    return f"{valor:,.2f}" if pd.notna(valor) else ""


def _fecha(ano, mes, dia):
    try:
        return f"{int(dia):02d}/{int(mes):02d}/{int(ano)}"
    except (TypeError, ValueError):
        return ""


def _arbol(padre, columnas, show="headings", selectmode="extended"):
    cont = ttk.Frame(padre)
    cont.pack(fill=tk.BOTH, expand=True)
    cont.columnconfigure(0, weight=1)
    cont.rowconfigure(0, weight=1)
    tree = ttk.Treeview(cont, columns=[c[0] for c in columnas], show=show, selectmode=selectmode)
    for col, titulo, ancho, ancla in columnas:
        tree.heading(col, text=titulo)
        tree.column(col, width=ancho, minwidth=40, anchor=ancla, stretch=(col == "detalle"))
    tree.grid(row=0, column=0, sticky="nsew")
    scroll = ttk.Scrollbar(cont, orient=tk.VERTICAL, command=tree.yview)
    scroll.grid(row=0, column=1, sticky="ns")
    tree.configure(yscrollcommand=scroll.set)
    return tree


class DialogoConfirmarBancarios(tk.Toplevel):
    COLUMNAS = (
        ("marca", "", 40, "center"),
        ("fecha", "Fecha", 85, "center"),
        ("detalle", "Detalle", 380, "w"),
        ("concepto", "Concepto", 190, "w"),
        ("valor", "Valor", 120, "e"),
    )

    def __init__(self, parent, detalle, tipo):
        super().__init__(parent)
        self.title("Confirmar movimientos bancarios")
        self.geometry("900x520")
        self.minsize(700, 400)
        self.detalle = detalle.sort_values(["archivo", "concepto", "ano", "mes", "dia"], kind="stable")
        self.marcados = set(self.detalle.index)
        self.resultado = None
        self.var_resumen = tk.StringVar()

        frm = ttk.Frame(self, padding=12)
        frm.pack(fill=tk.BOTH, expand=True)
        ttk.Label(frm, text=f"Los siguientes movimientos se categorizarán como {tipo}. ¿Confirma su selección?",
                  font=FUENTE).pack(anchor="w")
        ttk.Label(frm, text="Clic en la casilla o barra espaciadora para desmarcar · los desmarcados se tratarán "
                            "como egreso o recibo de caja.", foreground="gray").pack(anchor="w", pady=(2, 8))

        self.tree = _arbol(frm, self.COLUMNAS)
        self.tree.tag_configure("excluido", foreground="#9a9996")
        for i, ano, mes, dia, det, con, val in zip(
            self.detalle.index, self.detalle["ano"], self.detalle["mes"], self.detalle["dia"],
            self.detalle["detalle"], self.detalle["concepto"], self.detalle["valor"],
        ):
            self.tree.insert("", tk.END, iid=str(i), values=(MARCADO, _fecha(ano, mes, dia), det, con, _moneda(val)))
        self.tree.bind("<Button-1>", self._clic)
        self.tree.bind("<space>", self._alternar_seleccion)

        pie = ttk.Frame(frm)
        pie.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(pie, text="Marcar todo", command=lambda: self._marcar(self.detalle.index, True)).pack(side=tk.LEFT)
        ttk.Button(pie, text="Desmarcar todo", command=lambda: self._marcar(self.detalle.index, False)).pack(
            side=tk.LEFT, padx=6)
        ttk.Label(pie, textvariable=self.var_resumen, foreground="gray").pack(side=tk.LEFT, padx=8)
        ttk.Button(pie, text="Cancelar", command=self.destroy).pack(side=tk.RIGHT)
        ttk.Button(pie, text="Confirmar", command=self._confirmar).pack(side=tk.RIGHT, padx=6)

        self.bind("<Control-Return>", self._confirmar)
        self.bind("<Escape>", lambda e: self.destroy())
        self._actualizar()
        modal(self, parent)
        self.tree.focus_set()

    def _clic(self, event):
        iid = self.tree.identify_row(event.y)
        if iid and self.tree.identify_column(event.x) == "#1":
            i = int(iid)
            self._marcar([i], i not in self.marcados)
            return "break"

    def _alternar_seleccion(self, _=None):
        filas = [int(i) for i in self.tree.selection()]
        if filas:
            self._marcar(filas, any(f not in self.marcados for f in filas))
        return "break"

    def _marcar(self, filas, marcar):
        for f in filas:
            (self.marcados.add if marcar else self.marcados.discard)(f)
        self._actualizar(filas)

    def _actualizar(self, filas=None):
        for f in self.detalle.index if filas is None else filas:
            activo = f in self.marcados
            self.tree.set(str(f), "marca", MARCADO if activo else DESMARCADO)
            self.tree.item(str(f), tags=() if activo else ("excluido",))
        total = self.detalle.loc[sorted(self.marcados), "valor"].sum() if self.marcados else 0.0
        self.var_resumen.set(f"{len(self.marcados)} de {len(self.detalle)} marcados · Total {total:,.2f}")

    def _confirmar(self, _=None):
        excluidos = self.detalle.loc[[i for i in self.detalle.index if i not in self.marcados]]
        self.resultado = set(zip(excluidos["archivo"].astype(int), excluidos["id"].astype(int)))
        self.destroy()


def confirmar_bancarios(parent, generador):
    """Devuelve el conjunto de movimientos (archivo, id) a excluir de AJB; None si el usuario cancela."""
    detalle = getattr(generador, "bancarios_detalle", None)
    if detalle is None or detalle.empty:
        return set()
    tipo = generador.COMPROBANTES_PREDETERMINADOS.get(generador.CLASE_BANCARIO, "AJB")
    dialogo = DialogoConfirmarBancarios(parent, detalle.reset_index(drop=True), tipo)
    parent.wait_window(dialogo)
    return dialogo.resultado


class VentanaDetalleBancarios(tk.Toplevel):
    COLUMNAS = (
        ("fecha", "Fecha", 85, "center"),
        ("detalle", "Detalle", 420, "w"),
        ("codpuc", "Cuenta contable", 110, "center"),
        ("valor", "Valor", 130, "e"),
    )

    def __init__(self, parent, calc, gen):
        super().__init__(parent)
        self.title("Detalle de movimientos bancarios")
        self.geometry("1000x580")
        self.minsize(760, 420)

        frm = ttk.Frame(self, padding=12)
        frm.pack(fill=tk.BOTH, expand=True)
        ttk.Label(frm, text="Cada comprobante se registra en el banco con una sola línea por mes. "
                            "Expanda para ver contrapartidas y movimientos originales del extracto.",
                  foreground="gray").pack(anchor="w", pady=(0, 6))
        self.tree = _arbol(frm, self.COLUMNAS, show="tree headings", selectmode="browse")
        self.tree.heading("#0", text="Comprobante")
        self.tree.column("#0", width=170, minwidth=120, stretch=False)
        self.tree.tag_configure("comprobante", font=("Segoe UI", 10, "bold"))
        self.tree.tag_configure("original", foreground="#5e5c64")
        resumen = self._llenar(calc, gen)

        pie = ttk.Frame(frm)
        pie.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(pie, text="Expandir todo", command=lambda: self._expandir(True)).pack(side=tk.LEFT)
        ttk.Button(pie, text="Contraer todo", command=lambda: self._expandir(False)).pack(side=tk.LEFT, padx=6)
        ttk.Label(pie, text=resumen, foreground="gray").pack(side=tk.LEFT, padx=8)
        ttk.Button(pie, text="Cerrar", command=self.destroy).pack(side=tk.RIGHT)

        self.bind("<Escape>", lambda e: self.destroy())
        modal(self, parent)

    def _llenar(self, calc, gen):
        mensual = calc["tipo"].str[:2].isin(gen.PREFIJOS_BANCARIO)
        contra = calc[mensual & (calc["lado"] == gen.LADO_CONTRA)]
        banco = calc[mensual & (calc["lado"] == gen.LADO_BANCO)]
        detalle = getattr(gen, "bancarios_detalle", None)
        originales = {} if detalle is None or detalle.empty else \
            {k: g for k, g in detalle.groupby(["archivo", "grupo"], sort=False)}

        n_orig = 0
        for (tipo, numero), grupo in contra.groupby(["tipo", "numero"], sort=False):
            linea_banco = banco[(banco["tipo"] == tipo) & (banco["numero"] == numero)]
            b = linea_banco.iloc[0] if not linea_banco.empty else grupo.iloc[0]
            padre = self.tree.insert("", tk.END, text=f"{tipo} {numero}", open=True, tags=("comprobante",), values=(
                _fecha(b["ano"], b["mes"], b["dia"]), b["detalle"] if not linea_banco.empty else "",
                b["codpuc"] if not linea_banco.empty else "", _moneda(grupo["valor"].sum())))
            for _, fila in grupo.iterrows():
                orig = originales.get((fila["archivo"], fila["detalle"]))
                nodo = self.tree.insert(padre, tk.END, text=f"{len(orig)} mov." if orig is not None else "", values=(
                    _fecha(fila["ano"], fila["mes"], fila["dia"]), fila["detalle"], fila["codpuc"],
                    _moneda(fila["valor"])))
                if orig is None:
                    n_orig += 1
                    continue
                n_orig += len(orig)
                for ano, mes, dia, det, val in zip(orig["ano"], orig["mes"], orig["dia"], orig["detalle"], orig["valor"]):
                    self.tree.insert(nodo, tk.END, tags=("original",),
                                     values=(_fecha(ano, mes, dia), det, "", _moneda(val)))
        return f"{contra['tipo'].astype(str).add(contra['numero']).nunique()} comprobantes · " \
               f"{n_orig} movimientos del extracto · Neto {contra['valor'].sum():,.2f}"

    def _expandir(self, abrir):
        def recorrer(nodo):
            for hijo in self.tree.get_children(nodo):
                self.tree.item(hijo, open=abrir)
                recorrer(hijo)
        recorrer("")