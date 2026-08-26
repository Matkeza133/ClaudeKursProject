# ============================================
# VEZBA 1 - Osnove Pythona (poredjenje sa Pascalom)
# ============================================

# --- 1. PROMENLJIVE ---
# Pascal:  var ime: string; ime := 'Marko';
# Python nema deklaraciju tipa, tip se odredjuje automatski.
ime = "Marko"
godine = 25
prosek = 8.75

print("Ime:", ime)
print("Godine:", godine)
print("Prosek:", prosek)


# --- 2. UNOS SA TASTATURE ---
# Pascal:  readln(x);   -- uvek string koji se parsira u broj rucno
# Python:  input() uvek vraca string, pa broj moramo eksplicitno konvertovati.
broj_str = input("Unesi jedan broj: ")
broj = int(broj_str)   # kao Pascalov val() / StrToInt()
print("Unet broj:", broj)


# --- 3. USLOVI (if / elif / else) ---
# Pascal:
#   if broj > 0 then
#       writeln('pozitivan')
#   else if broj < 0 then
#       writeln('negativan')
#   else
#       writeln('nula');
#
# U Pythonu nema "then" i "begin...end", blokovi se prave uvlacenjem (indentacijom)!
if broj > 0:
    print("Broj je pozitivan")
elif broj < 0:
    print("Broj je negativan")
else:
    print("Broj je nula")


# --- 4. PETLJA FOR ---
# Pascal:  for i := 1 to 5 do writeln(i);
# Python:  range(1, 6) daje brojeve 1,2,3,4,5 (gornja granica se NE racuna)
print("Brojevi od 1 do 5:")
for i in range(1, 6):
    print(i)


# --- 5. PETLJA WHILE ---
# Pascal:
#   i := 1;
#   while i <= 5 do begin
#       writeln(i);
#       i := i + 1;
#   end;
i = 1
while i <= 5:
    print("while i =", i)
    i += 1   # skraceno od i = i + 1


# --- 6. NIZOVI / LISTE ---
# Pascal:  var brojevi: array[1..5] of integer;
# Python:  liste su fleksibilne, ne moras unapred da das duzinu ni tip.
brojevi = [10, 20, 30, 40, 50]
print("Lista brojeva:", brojevi)
print("Prvi element (indeks 0):", brojevi[0])   # u Pythonu se indeksira od 0, ne od 1!

suma = 0
for broj_iz_liste in brojevi:
    suma += broj_iz_liste
print("Suma liste:", suma)


# --- 7. FUNKCIJE ---
# Pascal:
#   function saberi(a, b: integer): integer;
#   begin
#       saberi := a + b;
#   end;
#
# Python:  def umesto function/procedure, return umesto dodele imenu funkcije
def saberi(a, b):
    return a + b

rezultat = saberi(3, 4)
print("3 + 4 =", rezultat)
