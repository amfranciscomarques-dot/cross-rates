"""Opções cambiais vanilla — modelo de Garman-Kohlhagen (Black-Scholes para FX).

Garman-Kohlhagen (1983) adapta Black-Scholes a opções sobre divisas tratando a
moeda estrangeira como um ativo que paga um "dividendo" contínuo igual à sua
taxa de juro. Na notação ``BASE/COTADA`` deste pacote, o spot ``S`` diz quantas
unidades de **COTADA** valem 1 **BASE**, logo:

* a **BASE** é o ativo subjacente (rende a taxa estrangeira ``r_f``);
* a **COTADA** é o numerário/doméstica (rende a taxa doméstica ``r_d``).

Uma *call* dá o direito de comprar 1 BASE por ``K`` COTADA; o prémio vem em
COTADA por 1 BASE. Com ``T`` em anos (``dias``/365), σ em fração anual e taxas
em capitalização contínua::

    d1 = [ln(S/K) + (r_d − r_f + σ²/2)·T] / (σ·√T)
    d2 = d1 − σ·√T
    call = S·e^(−r_f·T)·N(d1) − K·e^(−r_d·T)·N(d2)
    put  = K·e^(−r_d·T)·N(−d2) − S·e^(−r_f·T)·N(−d1)

A taxa anual cotada (média bid/ask de :class:`TaxaJuro`) é interpretada como
capitalização contínua para efeitos do modelo. Tudo em ``Decimal``: ``N`` (a
distribuição normal padrão) é calculada por uma série não-alternada da função de
erro (Abramowitz & Stegun 7.1.6), estável para todo o ``x`` e sem dependências
externas.

Enquadramento: Hull, *Options, Futures and Other Derivatives* (opções sobre
divisas / modelo de Black para FX); Madura, *International Financial
Management*, cap. 5 (opções cambiais).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, localcontext
from enum import Enum

from .cotacao import Cotacao, CotacaoInvalida, Numerico, normaliza_moeda, para_decimal
from .forward import TaxaJuro

CEM = Decimal(100)

# π com casas suficientes para a precisão interna de cálculo.
_PI = Decimal("3.1415926535897932384626433832795028841971693993751")
# Precisão (dígitos) das funções transcendentais (erf/exp/ln/sqrt).
_PRECISAO = 50
# Termo da série de erro abaixo do qual se considera convergida.
_EPS = Decimal(1).scaleb(-(_PRECISAO - 2))


class TipoOpcao(Enum):
    """Direção da opção: comprar (``CALL``) ou vender (``PUT``) a base."""

    CALL = "call"
    PUT = "put"


# --------------------------------------------------------------------------- #
# Distribuição normal padrão em Decimal (sem dependências externas)
# --------------------------------------------------------------------------- #


def _norm_pdf(x: Decimal) -> Decimal:
    """Densidade normal padrão ``n(x) = e^(−x²/2) / √(2π)``."""
    with localcontext() as ctx:
        ctx.prec = _PRECISAO
        return (-(x * x) / 2).exp() / (2 * _PI).sqrt()


def _erf(x: Decimal) -> Decimal:
    """Função de erro por série não-alternada (A&S 7.1.6), estável p/ todo o x.

        erf(x) = (2/√π)·e^(−x²)·Σₙ 2ⁿ·x^(2n+1) / (1·3·5···(2n+1))

    Todos os termos são positivos (sem cancelamento catastrófico), ao contrário
    da série de Maclaurin alternada.
    """
    if x == 0:
        return Decimal(0)
    with localcontext() as ctx:
        ctx.prec = _PRECISAO
        z = abs(x)
        termo = z
        soma = z
        n = 1
        while True:
            termo *= 2 * z * z / (2 * n + 1)
            soma += termo
            if termo <= soma * _EPS:
                break
            n += 1
        resultado = 2 / _PI.sqrt() * (-(z * z)).exp() * soma
        return resultado if x > 0 else -resultado


def _norm_cdf(x: Decimal) -> Decimal:
    """Distribuição normal padrão ``N(x) = (1 + erf(x/√2)) / 2``."""
    with localcontext() as ctx:
        ctx.prec = _PRECISAO
        return (1 + _erf(x / Decimal(2).sqrt())) / 2


# --------------------------------------------------------------------------- #
# Opção e resultado
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class OpcaoVanilla:
    """Opção cambial europeia vanilla sobre o par ``BASE/COTADA``.

    ``strike`` e ``notional`` exprimem-se, respetivamente, em COTADA por 1 BASE
    e em unidades da BASE. O ``notional`` por omissão é 1 (prémio unitário).
    """

    tipo: TipoOpcao
    base: str
    cotada: str
    strike: Decimal
    dias: int
    notional: Decimal = Decimal(1)

    def __post_init__(self) -> None:
        object.__setattr__(self, "base", normaliza_moeda(self.base))
        object.__setattr__(self, "cotada", normaliza_moeda(self.cotada))
        object.__setattr__(self, "strike", para_decimal(self.strike))
        object.__setattr__(self, "notional", para_decimal(self.notional))
        if not isinstance(self.tipo, TipoOpcao):
            raise CotacaoInvalida(f"Tipo de opção inválido: {self.tipo!r} (use TipoOpcao).")
        if self.base == self.cotada:
            raise CotacaoInvalida("A base e a cotada não podem ser a mesma moeda.")
        if self.strike <= 0:
            raise CotacaoInvalida("O strike tem de ser positivo.")
        if self.dias <= 0:
            raise CotacaoInvalida("O prazo (dias) tem de ser positivo.")
        if self.notional <= 0:
            raise CotacaoInvalida("O notional tem de ser positivo.")

    @property
    def par(self) -> str:
        return f"{self.base}/{self.cotada}"


@dataclass(frozen=True)
class ResultadoOpcao:
    """Prémio e Gregas de uma opção vanilla por Garman-Kohlhagen.

    O prémio vem em COTADA por 1 BASE (``preco``) e para o notional
    (``preco_total``). As Gregas usam as escalas habituais de mesa: ``vega`` por
    +1 ponto de volatilidade, ``theta`` por dia de calendário e ``rho`` por +1
    ponto percentual da taxa doméstica (a da COTADA).
    """

    tipo: str  # "call" / "put"
    base: str
    cotada: str
    strike: Decimal
    dias: int
    notional: Decimal
    spot: Decimal  # S (mid do par)
    vol: Decimal  # σ em % anual (como recebido)
    juro_base: Decimal  # r_f em % (média) — moeda BASE/estrangeira
    juro_cotada: Decimal  # r_d em % (média) — moeda COTADA/doméstica
    d1: Decimal
    d2: Decimal
    preco: Decimal  # prémio por 1 BASE, em COTADA
    preco_total: Decimal  # prémio para o notional
    delta: Decimal
    gamma: Decimal
    vega: Decimal  # por +1 ponto de vol
    theta: Decimal  # por dia de calendário
    rho: Decimal  # por +1 ponto percentual de r_d (cotada)
    nota: str

    @property
    def par(self) -> str:
        return f"{self.base}/{self.cotada}"


def _valida(opcao: OpcaoVanilla, spot: Cotacao, juro_base: TaxaJuro, juro_cotada: TaxaJuro) -> None:
    if spot.base != opcao.base or spot.cotada != opcao.cotada:
        raise CotacaoInvalida(
            f"O spot {spot.par} não corresponde ao par da opção {opcao.par}."
        )
    if juro_base.moeda != opcao.base:
        raise CotacaoInvalida(
            f"A taxa de juro da base ({juro_base.moeda}) não corresponde à base "
            f"da opção ({opcao.base})."
        )
    if juro_cotada.moeda != opcao.cotada:
        raise CotacaoInvalida(
            f"A taxa de juro da cotada ({juro_cotada.moeda}) não corresponde à "
            f"cotada da opção ({opcao.cotada})."
        )


def garman_kohlhagen(
    opcao: OpcaoVanilla,
    spot: Cotacao,
    vol: Numerico,
    juro_base: TaxaJuro,
    juro_cotada: TaxaJuro,
) -> ResultadoOpcao:
    """Preço e Gregas (delta, gamma, vega, theta, rho) por Garman-Kohlhagen.

    ``vol`` é a volatilidade anual em **percentagem** (ex.: ``10`` para 10%). As
    taxas de juro vêm em :class:`TaxaJuro` (usa-se a média bid/ask como taxa de
    capitalização contínua). O ``spot`` é o par ``BASE/COTADA``; usa-se o mid.
    """
    _valida(opcao, spot, juro_base, juro_cotada)
    sigma_pct = para_decimal(vol)
    if sigma_pct <= 0:
        raise CotacaoInvalida("A volatilidade tem de ser positiva.")

    with localcontext() as ctx:
        ctx.prec = _PRECISAO
        s = (spot.bid + spot.ask) / 2
        k = opcao.strike
        sigma = sigma_pct / CEM
        r_f = juro_base.media / CEM
        r_d = juro_cotada.media / CEM
        t = Decimal(opcao.dias) / Decimal(365)
        raiz_t = t.sqrt()
        sig_raiz_t = sigma * raiz_t

        d1 = ((s / k).ln() + (r_d - r_f + sigma * sigma / 2) * t) / sig_raiz_t
        d2 = d1 - sig_raiz_t
        desc_f = (-r_f * t).exp()
        desc_d = (-r_d * t).exp()
        pdf_d1 = _norm_pdf(d1)

        if opcao.tipo is TipoOpcao.CALL:
            n_d1, n_d2 = _norm_cdf(d1), _norm_cdf(d2)
            preco = s * desc_f * n_d1 - k * desc_d * n_d2
            delta = desc_f * n_d1
            rho = k * t * desc_d * n_d2 / CEM
            theta_ano = (
                -(s * desc_f * pdf_d1 * sigma) / (2 * raiz_t)
                + r_f * s * desc_f * n_d1
                - r_d * k * desc_d * n_d2
            )
        else:
            n_md1, n_md2 = _norm_cdf(-d1), _norm_cdf(-d2)
            preco = k * desc_d * n_md2 - s * desc_f * n_md1
            delta = -desc_f * n_md1
            rho = -k * t * desc_d * n_md2 / CEM
            theta_ano = (
                -(s * desc_f * pdf_d1 * sigma) / (2 * raiz_t)
                - r_f * s * desc_f * n_md1
                + r_d * k * desc_d * n_md2
            )

        gamma = desc_f * pdf_d1 / (s * sig_raiz_t)
        vega = s * desc_f * pdf_d1 * raiz_t / CEM  # por +1 ponto de vol
        theta = theta_ano / Decimal(365)  # por dia
        preco_total = preco * opcao.notional

    return ResultadoOpcao(
        tipo=opcao.tipo.value,
        base=opcao.base,
        cotada=opcao.cotada,
        strike=k,
        dias=opcao.dias,
        notional=opcao.notional,
        spot=s,
        vol=sigma_pct,
        juro_base=juro_base.media,
        juro_cotada=juro_cotada.media,
        d1=d1,
        d2=d2,
        preco=preco,
        preco_total=preco_total,
        delta=delta,
        gamma=gamma,
        vega=vega,
        theta=theta,
        rho=rho,
        nota=_nota(opcao, s),
    )


def _nota(opcao: OpcaoVanilla, spot: Decimal) -> str:
    return (
        f"Garman-Kohlhagen: {opcao.tipo.value} sobre {opcao.par}. A base "
        f"({opcao.base}) é o ativo (rende r_f); a cotada ({opcao.cotada}) é o "
        f"numerário (rende r_d). Prémio em {opcao.cotada} por 1 {opcao.base}; "
        f"T = {opcao.dias}/365 anos. Não é previsão: é o custo de replicação "
        f"sem arbitragem da opção."
    )
