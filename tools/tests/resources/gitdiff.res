diff --git a/README.md b/README.md
index a39c084..bb43e90 100644
--- a/README.md
+++ b/README.md
@@ -17 +17 @@ mvn eu.stamp-project:pitmp-maven-plugin:descartes
-jeudi 14 juin 2018, 12:12:07 (UTC+0200)
+vendredi 22 juin 2018, 11:30:55 (UTC+0200)
diff --git a/src/main/java/eu/stamp_project/examples/dhell/HelloApp.java b/src/main/java/eu/stamp_project/examples/dhell/HelloApp.java
index 1681b20..8c03b7b 100644
--- a/src/main/java/eu/stamp_project/examples/dhell/HelloApp.java
+++ b/src/main/java/eu/stamp_project/examples/dhell/HelloApp.java
@@ -91,0 +92 @@ public class HelloApp
+        Double myValue = computeMyUselessResult();
@@ -94,0 +96 @@ public class HelloApp
+        String valueString = Double.toString(myValue);
@@ -114,0 +117 @@ public class HelloApp
+        myPrint(indent + " " + valueString);
@@ -122 +125 @@ public class HelloApp
-    public void computeMyUselessResult()
+    public Double computeMyUselessResult()
@@ -129,0 +133,2 @@ public class HelloApp
+        Double result = getMyPrintCount() * 3.141592653589793238462643383279;
+        return(result);
diff --git a/src/test/java/eu/stamp_project/examples/dhell/HelloAppTest.java b/src/test/java/eu/stamp_project/examples/dhell/HelloAppTest.java
index 2b5c0e3..47e01c5 100644
--- a/src/test/java/eu/stamp_project/examples/dhell/HelloAppTest.java
+++ b/src/test/java/eu/stamp_project/examples/dhell/HelloAppTest.java
@@ -139,0 +140 @@ public class HelloAppTest
+        String valueString = "---------------------- 69.11503837897544";
@@ -152,0 +154 @@ public class HelloAppTest
+        assertEquals(true, valueString.equals(fileContent.getData(4)));
