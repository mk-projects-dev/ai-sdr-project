.PHONY: dev db-up db-down db-logs

dev:
	npm run dev

db-up:
	npm run db:up

db-down:
	npm run db:down

db-logs:
	npm run db:logs
