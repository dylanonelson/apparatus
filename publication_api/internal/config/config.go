package config

import (
	"os"
)

const (
	defaultPort            = "8091"
	defaultPublicationsDir = "ebook_files"
)

// Port returns the HTTP port to bind to (without leading colon).
func Port() string {
	if v := os.Getenv("PUBLICATION_SERVER_PORT"); v != "" {
		return v
	}
	return defaultPort
}

// PublicationsDir returns the base directory where publications are located.
func PublicationsDir() string {
	if v := os.Getenv("PUBLICATIONS_DIR"); v != "" {
		return v
	}
	return defaultPublicationsDir
}
