package main

import (
	"errors"
	"fmt"
	"io"
	"math"
	"regexp"
	"strconv"
)

type hhMM struct {
	heures  int
	minutes int
}

func (x hhMM) AddMinutes(minutes int) (y hhMM) {
	y.minutes = x.minutes + minutes
	y.heures = x.heures + y.minutes/60
	y.minutes = y.minutes % 60
	return
}

func (x hhMM) String() string {
	return fmt.Sprintf("%02dh%02d", x.heures, x.minutes)
}

// retourne la différence en minutes de deux hhMM
func (h1 hhMM) DiffMinutes(h2 hhMM) int {
	return (h2.heures-h1.heures)*60 + (h2.minutes - h1.minutes)
}

func readHeure(prompt string) (hour hhMM) {
	var d string
	var err error

	fmt.Print(prompt)

	if n, _ := fmt.Scan(&d); n != 1 {
		err = io.EOF
		panic("Erreur heure")
	}

	hour, err = getHeure(d)
	if err != nil {
		panic("Erreur heure")
	}
	return
}

func getHeure(d string) (hour hhMM, err error) {

	re := regexp.MustCompile(`(\d+)[hH](\d+)`)
	x := re.FindStringSubmatch(d)
	if len(x) == 0 {
		err = errors.New("Pas une heure")
		return
	}

	hour.heures, _ = strconv.Atoi(x[1])
	hour.minutes, _ = strconv.Atoi(x[2])

	if hour.heures < 0 || hour.heures >= 24 {
		err = errors.New("Mauvaises heures")
		return
	}
	if hour.minutes < 0 || hour.minutes >= 60 {
		err = errors.New("Mauvaises minutes")
		return
	}

	return
}

func readHauteur(prompt string) (hauteur float64) {
	fmt.Print(prompt)
	if n, _ := fmt.Scanf("%f", &hauteur); n != 1 {
		panic("erreur hauteur")
	}
	return
}

func getHauteur(s string) (hauteur float64, err error) {
	if n, _ := fmt.Sscanf(s, "%f", &hauteur); n != 1 {
		err = strconv.ErrSyntax
	}
	return
}

func main() {

	fmt.Println("Calcul de marées")
	fmt.Println()

	h1 := readHeure("Heure 1: ")
	m1 := readHauteur("Hauteur 1: ")
	h2 := readHeure("Heure 2: ")
	m2 := readHauteur("Hauteur 2: ")
	fmt.Println()

	hm := float64(h1.DiffMinutes(h2)) / 6
	dz := (m2 - m1) / 12

	fmt.Println()
	if dz < 0 {
		fmt.Printf("PM: %v %5.2f m\n", h1, m1)
		fmt.Printf("BM: %v %5.2f m\n", h2, m2)
	} else {
		fmt.Printf("BM: %v %5.2f m\n", h1, m1)
		fmt.Printf("PM: %v %5.2f m\n", h2, m2)
	}

	fmt.Println()
	fmt.Printf("HM=%.3f min  dz=%.3f m\n", hm, math.Abs(dz))

	fmt.Println()

	douzaines := [6]int{1, 2, 3, 3, 2, 1}
	cumul := [6]int{0, 1, 3, 6, 9, 11}

	decalageHeure := 0
	nomHeure := "hiver"

	for {
		var s string
		n, _ := fmt.Scan(&s)

		if s == "." || n == 0 {
			break
		}

		if s == "été" {
			decalageHeure = 60
			nomHeure = "été"
			continue
		}

		// recherche d'une hauteur en fonction de l'heure
		if h, err := getHeure(s); err == nil {

			delta := float64(h1.DiffMinutes(h)-decalageHeure) / hm
			deltaInt := int(math.Floor(delta))

			fractionHauteur := float64(cumul[deltaInt]) + float64(douzaines[deltaInt])*(delta-math.Floor(delta))
			deltaHauteur := fractionHauteur * dz
			fmt.Printf("hauteur marée à %v (heure %s) : %.2f m\n", h, nomHeure, m1+deltaHauteur)

			continue
		}

		if m, err := getHauteur(s); err == nil {

			nbDz := (m - m1) / dz
			nbDzInt := int(math.Floor(nbDz))

			for i := 0; i < 6; i++ {

				if cumul[i] <= nbDzInt && nbDzInt < cumul[i]+douzaines[i] {

					delta := (float64(i) + (nbDz-float64(cumul[i]))/float64(douzaines[i])) * float64(hm)
					h := h1.AddMinutes(int(math.Round(delta)) + decalageHeure)

					fmt.Printf("heure marée à %.2f m : %v (heure %s)\n", m, h, nomHeure)
					break
				}
			}

			continue
		}

		break
	}
}
