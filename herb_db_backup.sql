mysqldump.exe : mysqldump: [Warning] Using a password on the command line interface can be insecure.
所在位置 行:1 字符: 1
+ & "C:\Program Files\MySQL\MySQL Server 8.0\bin\mysqldump.exe" -uroot  ...
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : NotSpecified: (mysqldump: [War...an be insecure.:String) [], RemoteException
    + FullyQualifiedErrorId : NativeCommandError
 
-- MySQL dump 10.13  Distrib 8.0.46, for Win64 (x86_64)
--
-- Host: localhost    Database: herb_management_system
-- ------------------------------------------------------
-- Server version	8.0.46

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `herbs`
--

DROP TABLE IF EXISTS `herbs`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `herbs` (
  `code` varchar(50) NOT NULL COMMENT '药材编码',
  `name` varchar(50) NOT NULL COMMENT '药材名称',
  `category` varchar(50) DEFAULT NULL COMMENT '类别',
  `origin` varchar(100) DEFAULT NULL COMMENT '产地',
  `storage` varchar(100) DEFAULT NULL COMMENT '储存条件',
  `unit` varchar(20) DEFAULT NULL COMMENT '单位',
  `price` decimal(10,2) DEFAULT NULL COMMENT '单价',
  `quantity` int DEFAULT '0' COMMENT '库存数量',
  `warning_threshold` int DEFAULT '200' COMMENT '预警阈值',
  `description` text COMMENT '描述',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='药材表';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `herbs`
--

LOCK TABLES `herbs` WRITE;
/*!40000 ALTER TABLE `herbs` DISABLE KEYS */;
INSERT INTO `herbs` VALUES ('HC1788770050694750','人参','根茎类','吉林长白山','密闭，置阴凉干燥处，防蛀','g',500.00,700,50,'大补元气，复脉固脱，补脾益肺，生津养血，安神益智。','2026-09-07 16:35:00','2026-09-07 16:35:17'),('HC1788934105467300','蒲黄','花类','江苏、浙江','置通风干燥处，防潮，防蛀','g',100.00,600,200,'止血，化瘀，通淋。','2026-09-09 14:09:05','2026-09-09 14:22:50'),('HC1788936392897544','王不留行','果实种子类','河北、山东','置干燥处','g',10.00,10000,200,'活血通经，下乳消肿，利尿通淋。','2026-09-09 14:46:44','2026-09-09 14:46:44');
/*!40000 ALTER TABLE `herbs` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `operation_logs`
--

DROP TABLE IF EXISTS `operation_logs`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `operation_logs` (
  `id` int NOT NULL AUTO_INCREMENT COMMENT '日志ID',
  `herb_code` varchar(50) DEFAULT NULL COMMENT '药材编码',
  `herb_name` varchar(50) DEFAULT NULL COMMENT '药材名称',
  `action` varchar(20) NOT NULL COMMENT '操作: add/edit/delete',
  `changes` json DEFAULT NULL COMMENT '字段变更明细',
  `operator` varchar(50) DEFAULT NULL COMMENT '操作人用户名',
  `operator_name` varchar(50) DEFAULT NULL COMMENT '操作人姓名',
  `timestamp` bigint DEFAULT NULL COMMENT '操作时间戳',
  `time_str` varchar(50) DEFAULT NULL COMMENT '操作时间文本',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=10 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='操作日志表';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `operation_logs`
--

LOCK TABLES `operation_logs` WRITE;
/*!40000 ALTER TABLE `operation_logs` DISABLE KEYS */;
INSERT INTO `operation_logs` VALUES (1,'H001','人参','add','[{\"field\": \"code\", \"label\": \"code\", \"newValue\": \"H001\", \"oldValue\": null}, {\"field\": \"name\", \"label\": \"药材名称\", \"newValue\": \"人参\", \"oldValue\": null}, {\"field\": \"category\", \"label\": \"类别\", \"newValue\": \"根茎类\", \"oldValue\": null}, {\"field\": \"origin\", \"label\": \"产地\", \"newValue\": \"吉林\", \"oldValue\": null}, {\"field\": \"storage\", \"label\": \"储存条件\", \"newValue\": \"\", \"oldValue\": null}, {\"field\": \"unit\", \"label\": \"单位\", \"newValue\": \"g\", \"oldValue\": null}, {\"field\": \"price\", \"label\": \"单价\", \"newValue\": 100.0, \"oldValue\": null}, {\"field\": \"quantity\", \"label\": \"库存数量\", \"newValue\": 500, \"oldValue\": null}, {\"field\": \"warningThreshold\", \"label\": \"预警阈值\", \"newValue\": 100, \"oldValue\": null}, {\"field\": \"description\", \"label\": \"描述\", \"newValue\": \"大补元气\", \"oldValue\": null}]','admin','系统管理员',1788769542491,'2026/09/07 16:25:42'),(2,'H001','人参','edit','[{\"field\": \"price\", \"label\": \"单价\", \"newValue\": 120.0, \"oldValue\": \"120.00\"}]','admin','系统管理员',1788769604086,'2026/09/07 16:26:44'),(3,'H001','人参','edit','[{\"field\": \"quantity\", \"label\": \"库存数量\", \"newValue\": 400, \"oldValue\": 450}]','admin','系统管理员',1788769604291,'2026/09/07 16:26:44'),(4,'H001','人参','delete','[{\"field\": \"code\", \"label\": \"编码\", \"newValue\": null, \"oldValue\": \"H001\"}, {\"field\": \"name\", \"label\": \"药材名称\", \"newValue\": null, \"oldValue\": \"人参\"}, {\"field\": \"category\", \"label\": \"类别\", \"newValue\": null, \"oldValue\": \"根茎类\"}, {\"field\": \"origin\", \"label\": \"产地\", \"newValue\": null, \"oldValue\": \"吉林\"}, {\"field\": \"storage\", \"label\": \"储存条件\", \"newValue\": null, \"oldValue\": \"\"}, {\"field\": \"unit\", \"label\": \"单位\", \"newValue\": null, \"oldValue\": \"g\"}, {\"field\": \"price\", \"label\": \"单价\", \"newValue\": null, \"oldValue\": \"120.00\"}, {\"field\": \"quantity\", \"label\": \"库存数量\", \"newValue\": null, \"oldValue\": 400}, {\"field\": \"warningThreshold\", \"label\": \"预警阈值\", \"newValue\": null, \"oldValue\": 100}, {\"field\": \"description\", \"label\": \"描述\", \"newValue\": null, \"oldValue\": \"大补元气\"}]','admin','系统管理员',1788769605034,'2026/09/07 16:26:45'),(5,'HC1788770050694750','人参','add','[{\"field\": \"code\", \"label\": \"code\", \"newValue\": \"HC1788770050694750\", \"oldValue\": null}, {\"field\": \"name\", \"label\": \"药材名称\", \"newValue\": \"人参\", \"oldValue\": null}, {\"field\": \"category\", \"label\": \"类别\", \"newValue\": \"根茎类\", \"oldValue\": null}, {\"field\": \"origin\", \"label\": \"产地\", \"newValue\": \"吉林长白山\", \"oldValue\": null}, {\"field\": \"storage\", \"label\": \"储存条件\", \"newValue\": \"密闭，置阴凉干燥处，防蛀\", \"oldValue\": null}, {\"field\": \"unit\", \"label\": \"单位\", \"newValue\": \"g\", \"oldValue\": null}, {\"field\": \"price\", \"label\": \"单价\", \"newValue\": 500.0, \"oldValue\": null}, {\"field\": \"quantity\", \"label\": \"库存数量\", \"newValue\": 800, \"oldValue\": null}, {\"field\": \"warningThreshold\", \"label\": \"预警阈值\", \"newValue\": 50, \"oldValue\": null}, {\"field\": \"description\", \"label\": \"描述\", \"newValue\": \"大补元气，复脉固脱，补脾益肺，生津养血，安神益智。\", \"oldValue\": null}]','admin','系统管理员',1788770100049,'2026/09/07 16:35:00'),(6,'HC1788770050694750','人参','edit','[{\"field\": \"quantity\", \"label\": \"库存数量\", \"newValue\": 700, \"oldValue\": 800}]','admin','系统管理员',1788770117150,'2026/09/07 16:35:17'),(7,'HC1788934105467300','蒲黄','add','[{\"field\": \"code\", \"label\": \"code\", \"newValue\": \"HC1788934105467300\", \"oldValue\": null}, {\"field\": \"name\", \"label\": \"药材名称\", \"newValue\": \"蒲黄\", \"oldValue\": null}, {\"field\": \"category\", \"label\": \"类别\", \"newValue\": \"花类\", \"oldValue\": null}, {\"field\": \"origin\", \"label\": \"产地\", \"newValue\": \"江苏、浙江\", \"oldValue\": null}, {\"field\": \"storage\", \"label\": \"储存条件\", \"newValue\": \"置通风干燥处，防潮，防蛀\", \"oldValue\": null}, {\"field\": \"unit\", \"label\": \"单位\", \"newValue\": \"g\", \"oldValue\": null}, {\"field\": \"price\", \"label\": \"单价\", \"newValue\": 100.0, \"oldValue\": null}, {\"field\": \"quantity\", \"label\": \"库存数量\", \"newValue\": 100, \"oldValue\": null}, {\"field\": \"warningThreshold\", \"label\": \"预警阈值\", \"newValue\": 200, \"oldValue\": null}, {\"field\": \"description\", \"label\": \"描述\", \"newValue\": \"止血，化瘀，通淋。\", \"oldValue\": null}]','admin','系统管理员',1788934145851,'2026/09/09 14:09:05'),(8,'HC1788934105467300','蒲黄','edit','[{\"field\": \"quantity\", \"label\": \"库存数量\", \"newValue\": 600, \"oldValue\": 100}]','admin','系统管理员',1788934970731,'2026/09/09 14:22:50'),(9,'HC1788936392897544','王不留行','add','[{\"field\": \"code\", \"label\": \"code\", \"newValue\": \"HC1788936392897544\", \"oldValue\": null}, {\"field\": \"name\", \"label\": \"药材名称\", \"newValue\": \"王不留行\", \"oldValue\": null}, {\"field\": \"category\", \"label\": \"类别\", \"newValue\": \"果实种子类\", \"oldValue\": null}, {\"field\": \"origin\", \"label\": \"产地\", \"newValue\": \"河北、山东\", \"oldValue\": null}, {\"field\": \"storage\", \"label\": \"储存条件\", \"newValue\": \"置干燥处\", \"oldValue\": null}, {\"field\": \"unit\", \"label\": \"单位\", \"newValue\": \"g\", \"oldValue\": null}, {\"field\": \"price\", \"label\": \"单价\", \"newValue\": 10.0, \"oldValue\": null}, {\"field\": \"quantity\", \"label\": \"库存数量\", \"newValue\": 10000, \"oldValue\": null}, {\"field\": \"warningThreshold\", \"label\": \"预警阈值\", \"newValue\": 200, \"oldValue\": null}, {\"field\": \"description\", \"label\": \"描述\", \"newValue\": \"活血通经，下乳消肿，利尿通淋。\", \"oldValue\": null}]','admin','系统管理员',1788936404111,'2026/09/09 14:46:44');
/*!40000 ALTER TABLE `operation_logs` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `users`
--

DROP TABLE IF EXISTS `users`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `users` (
  `username` varchar(50) NOT NULL COMMENT '用户名',
  `password` varchar(64) NOT NULL COMMENT '密码(SHA256)',
  `role` varchar(20) NOT NULL DEFAULT 'patient' COMMENT '角色: admin/doctor/patient',
  `name` varchar(50) NOT NULL COMMENT '真实姓名',
  `phone` varchar(30) DEFAULT NULL COMMENT '联系电话',
  `status` varchar(20) NOT NULL DEFAULT 'active' COMMENT '状态: active/inactive',
  `department` varchar(50) DEFAULT NULL COMMENT '所属科室(医生)',
  `license` varchar(50) DEFAULT NULL COMMENT '执业医师证号(医生)',
  `gender` varchar(10) DEFAULT NULL COMMENT '性别(病人)',
  `age` int DEFAULT NULL COMMENT '年龄(病人)',
  `idcard` varchar(30) DEFAULT NULL COMMENT '身份证号(病人)',
  `create_time` varchar(50) DEFAULT NULL COMMENT '注册时间',
  PRIMARY KEY (`username`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='用户表';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `users`
--

LOCK TABLES `users` WRITE;
/*!40000 ALTER TABLE `users` DISABLE KEYS */;
INSERT INTO `users` VALUES ('admin','8d969eef6ecad3c29a3a629280e686cf0c3f5d5a86aff3ca12020c923adc6c92','admin','系统管理员','13800138000','active',NULL,NULL,NULL,NULL,NULL,'2026/9/7 00:00:00'),('doctor','8d969eef6ecad3c29a3a629280e686cf0c3f5d5a86aff3ca12020c923adc6c92','doctor','李医生','13900139000','active','中医内科','110101202600001',NULL,NULL,NULL,'2026/9/7 00:00:00'),('patient','8d969eef6ecad3c29a3a629280e686cf0c3f5d5a86aff3ca12020c923adc6c92','patient','王病人','13700137000','active',NULL,NULL,'男',35,'340104199101011234','2026/9/7 00:00:00'),('zhang','8d969eef6ecad3c29a3a629280e686cf0c3f5d5a86aff3ca12020c923adc6c92','patient','zzz','15555555555','active',NULL,NULL,'男',20,'22556985745','2026/09/09 14:20:15');
/*!40000 ALTER TABLE `users` ENABLE KEYS */;
UNLOCK TABLES;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2026-09-09 14:52:31
