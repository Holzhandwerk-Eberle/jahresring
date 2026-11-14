//go:build !windows

package main

import (
	"fmt"
	"os"
	"path/filepath"
)

func frage(text string) bool             { fmt.Println("FRAGE:", text); return true }
func meldung(text string, fehler bool)   { fmt.Println("MELDUNG:", text) }
func heimOrdner() string                 { return os.Getenv("JR_HEIM") }
func merkDatei() string                  { return filepath.Join(os.Getenv("JR_HEIM"), "merk", "ordner.txt") }
func verknuepfungen(ziel string) error   { fmt.Println("Verknüpfungen für", ziel); return nil }
func starten(ziel string) error          { fmt.Println("Start", ziel); return nil }
func ordnerWaehlen(titel string) string  { return os.Getenv("JR_QUELLE") }
func standardOrdner() string             { return "" }
func firewallVorhanden() bool            { return os.Getenv("JR_FW") == "" }
func firewallFreigeben() (string, error) { return os.Getenv("JR_FW"), nil }
