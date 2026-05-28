-- MySQL schema/data for trip_plans
DROP TABLE IF EXISTS `trip_plans`;
CREATE TABLE `trip_plans` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `owner_user_id` int unsigned NOT NULL,
  `title` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `origin` varchar(128) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `city` varchar(128) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `start_date` date DEFAULT NULL,
  `end_date` date DEFAULT NULL,
  `budget_range` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `current_version_id` int unsigned DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_owner_updated` (`owner_user_id`,`updated_at`),
  KEY `idx_city` (`city`),
  KEY `fk_trip_plans_current_version` (`current_version_id`),
  CONSTRAINT `fk_trip_plans_current_version` FOREIGN KEY (`current_version_id`) REFERENCES `trip_plan_versions` (`id`) ON DELETE SET NULL,
  CONSTRAINT `fk_trip_plans_user` FOREIGN KEY (`owner_user_id`) REFERENCES `users` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

LOCK TABLES `trip_plans` WRITE;
/*!40000 ALTER TABLE `trip_plans` DISABLE KEYS */;
INSERT INTO `trip_plans` (`id`,`owner_user_id`,`title`,`origin`,`city`,`start_date`,`end_date`,`budget_range`,`current_version_id`,`created_at`,`updated_at`) VALUES
(2,2,'西藏五日游','北京','西藏','2026-05-10','2026-05-15','high',3,'2026-05-22 15:08:43','2026-05-22 15:08:43');
/*!40000 ALTER TABLE `trip_plans` ENABLE KEYS */;
UNLOCK TABLES;
