##BR-001 — PENDING

Rezerwacja własna bez potwierdzonego zadatku otrzymuje PENDING.

##BR-002 — blokowanie

PENDING, CONFIRMED i BLOCKED blokują dostępność domku.

##BR-003 — zadatek

Wpłata wymaganego zadatku zmienia:

PENDING → CONFIRMED
UNPAID → PAID

##BR-004 — wygaśnięcie

Domyślny czas na potwierdzenie zadatku wynosi 24 godziny.

##BR-005 — przedłużenie

Operator może ręcznie przedłużyć expires_at.

##BR-006 — brak wpłaty

Po przekroczeniu expires_at rezerwacja przechodzi:

PENDING → EXPIRED

i przestaje blokować termin.

##BR-007 — anulowanie

CANCELLED nie blokuje dostępności.

##BR-008 — zadatek przy anulowaniu

Jeżeli potwierdzona rezerwacja własna zostanie anulowana z przyczyn leżących po stronie klienta, zadatek może otrzymać status:

FORFEITED

a termin zostaje uwolniony.

##BR-009 — godziny pobytu

Standardowa godzina zameldowania (check-in) wynosi 16:00.

Standardowa godzina wymeldowania (check-out) wynosi 10:00.

Godziny są parametrami konfiguracyjnymi systemu i nie są zapisane na stałe w logice aplikacji.

Operator może dobrowolnie umożliwić wcześniejsze zameldowanie, jeżeli domek jest już przygotowany. Wcześniejsze zameldowanie nie jest na tym etapie rejestrowane ani rozliczane przez system.

##BR-010 — dostępność, konflikt i optymalizacja obłożenia

System określa dostępność domku na podstawie godzin check-out i check-in określonych w BR-009.

Rezerwacja nie powoduje konfliktu, jeżeli poprzedni pobyt kończy się o godzinie check-out przed rozpoczęciem kolejnego pobytu, z uwzględnieniem minimalnego czasu umożliwiającego przygotowanie domku.

##PET-01
Zwierzęta nie są wliczane do `cottage.capacity`.

##PET-02
Maksymalnie 2 zwierzęta na rezerwację.

##PET-03
Opłata za zwierzę wynosi 25 PLN za cały pobyt,
niezależnie od liczby zwierząt.
