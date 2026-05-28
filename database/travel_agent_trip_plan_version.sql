-- MySQL dump 10.13  Distrib 8.0.45, for Win64 (x86_64)
--
-- Host: localhost    Database: travel_agent
-- ------------------------------------------------------
-- Server version	8.0.46

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `trip_plan_versions`
--

DROP TABLE IF EXISTS `trip_plan_versions`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `trip_plan_versions` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `plan_id` int unsigned NOT NULL,
  `parent_version_id` int unsigned DEFAULT NULL,
  `owner_user_id` int unsigned NOT NULL,
  `version_no` int NOT NULL,
  `source_type` enum('created','regenerated','edited','restored') COLLATE utf8mb4_unicode_ci NOT NULL,
  `change_summary` text COLLATE utf8mb4_unicode_ci,
  `content_json` json NOT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_plan_version` (`plan_id`,`version_no`),
  KEY `idx_plan_id` (`plan_id`),
  KEY `idx_owner_user_id` (`owner_user_id`),
  KEY `fk_version_parent_idx` (`parent_version_id`),
  CONSTRAINT `fk_version_parent` FOREIGN KEY (`parent_version_id`) REFERENCES `trip_plan_versions` (`id`) ON DELETE SET NULL,
  CONSTRAINT `fk_version_user` FOREIGN KEY (`owner_user_id`) REFERENCES `users` (`id`),
  CONSTRAINT `fk_versions_plan` FOREIGN KEY (`plan_id`) REFERENCES `trip_plans` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=6 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `trip_plan_versions`
--

LOCK TABLES `trip_plan_versions` WRITE;
/*!40000 ALTER TABLE `trip_plan_versions` DISABLE KEYS */;
INSERT INTO `trip_plan_versions` VALUES (3,2,NULL,2,1,'created','Initial Xizang itinerary','{\"days\": 5, \"hotel\": \"神秘小旅馆三号\", \"spots\": [\"景点6\", \"景点7\"]}','2026-05-22 15:08:43');
/*!40000 ALTER TABLE `trip_plan_versions` ENABLE KEYS */;
UNLOCK TABLES;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2026-05-22 17:55:44

