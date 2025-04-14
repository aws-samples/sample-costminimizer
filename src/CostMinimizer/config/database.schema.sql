BEGIN TRANSACTION;
CREATE TABLE IF NOT EXISTS "cow_customerdefinition" (
	"cx_id"	integer NOT NULL,
	"cx_name"	varchar(20) NOT NULL UNIQUE,
	"create_time"	datetime NOT NULL,
	"last_used_time"	datetime,
	"aws_profile"	varchar(256) NOT NULL,
	"secrets_aws_profile"	varchar(256) NOT NULL,
	"athena_s3_buckt"	varchar(256) NOT NULL,
	"cur_db_name"	varchar(256) NOT NULL,
	"cur_db_table"	varchar(256) NOT NULL,
	"cur_region"	varchar(256) NOT NULL,
	"min_spend"	integer NOT NULL,
	"acc_regex"	varchar(100) NOT NULL,
	"account_email" varchar(256) NOT NULL DEFAULT '',
	PRIMARY KEY("cx_id" AUTOINCREMENT)
);
CREATE TABLE IF NOT EXISTS "cow_customerpayeraccounts" (
	"payer_id"	TEXT NOT NULL,
	"account_id"	TEXT NOT NULL,
	"cx_id_id"	integer NOT NULL,
	PRIMARY KEY("payer_id"),
	FOREIGN KEY("cx_id_id") REFERENCES "cow_customerdefinition"("cx_id") DEFERRABLE INITIALLY DEFERRED
);
CREATE TABLE IF NOT EXISTS "cow_availablereports" (
	"report_id"	INTEGER,
	"report_name"	TEXT UNIQUE,
	"report_description"	TEXT,
	"report_provider"	TEXT,
	"service_name"	TEXT,
	"display"	TEXT,
	"common_name" TEXT,
	PRIMARY KEY("report_id" AUTOINCREMENT)
);
CREATE TABLE IF NOT EXISTS "cow_configuration" (
	"config_id"	INTEGER,
	"aws_cow_account"	TEXT,
	"aws_cow_profile"	TEXT,
	"sm_secret_name"	TEXT,
	"output_folder"	TEXT,
	"installation_mode"	TEXT,
	"container_mode_home"	TEXT,
	"cur_db" TEXT,
    "cur_table" TEXT,
    "cur_region" TEXT,
	"aws_cow_s3_bucket"	TEXT,
	"ses_send"	TEXT,
	"ses_from"	TEXT,
	"ses_region"	TEXT,
	"ses_smtp"	TEXT,
	"ses_login"	TEXT,
	"ses_password"	TEXT,
	"costexplorer_tags"	TEXT,
	"costexplorer_tags_value_filter"	TEXT,
	"graviton_tags"	TEXT,
	"graviton_tags_value_filter"	TEXT,
	"current_month"	TEXT,
	"day_month"	INTEGER,
	"last_month_only"	TEXT,
	"aws_access_key_id"	TEXT,
	"aws_secret_access_key"	TEXT,
    "cur_s3_bucket"	TEXT,
	PRIMARY KEY("config_id" AUTOINCREMENT)
);
CREATE TABLE IF NOT EXISTS "cow_customercache" (
	"cache_id"	INTEGER NOT NULL,
	"partition_type"	TEXT NOT NULL,
	"cx_id_id"	INTEGER NOT NULL,
	PRIMARY KEY("cache_id" AUTOINCREMENT),
	FOREIGN KEY("cx_id_id") REFERENCES "cow_customerdefinition"("cx_id") DEFERRABLE INITIALLY DEFERRED
)
COMMIT;
CREATE TABLE IF NOT EXISTS "cow_internalspamareters" (
	"param_id" INTEGER PRIMARY KEY ,
	"parent" TEXT,
	"key"	TEXT,
	"value"	TEXT,
	PRIMARY KEY("param_id" AUTOINCREMENT)
)
COMMIT;
CREATE TABLE IF NOT EXISTS "cow_awspricingdb" (
            "awspricing_id"	INTEGER,
            "family"	TEXT,
            "instancetype"	TEXT,
            "databaseengine"	TEXT,
            "deploymentoption"	TEXT,
            "location"	TEXT,
            "odpriceperunit"	FLOAT,
            "ripriceperunit"	FLOAT,
            PRIMARY KEY("family")
)
COMMIT;
CREATE TABLE IF NOT EXISTS "cow_awspricingec2" (
            "awspricing_id"	INTEGER,
            "ConcatField"	TEXT,
            "Column1"	TEXT,
            "vcpu"	INTEGER,
            "Family"	TEXT,
            "odpriceperunit"	FLOAT,
            "ripriceperunit"	FLOAT,
            "svpriceperunit"	FLOAT,
            PRIMARY KEY("ConcatField")
)
COMMIT;
CREATE TABLE IF NOT EXISTS cow_gravitonconversion (
            Family TEXT,
            Generation TEXT,
            Latest_Intel TEXT,
            Latest_AMD TEXT,
            Graviton2 TEXT,
            Graviton3 TEXT,
            Graviton4 TEXT,
            Previous_Intel TEXT,
            Default_Graviton_Equivalent TEXT,
            Latest_Elasticsearch_Intel TEXT
)
COMMIT;
