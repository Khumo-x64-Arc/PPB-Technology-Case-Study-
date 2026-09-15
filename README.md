# PPB-Technology-Case-Study-
As part of the Standard Bank Assessment centre candidate have to create a MVP (Minimum Viable Product) based on an Candidate Pack and data set. This repository contains my identified solution to a problem found in the candidate pack and dataset. In addition to to that a presentation has to be created and presented a day later. 

## Table of Contents 
1. Project Overview
2.  File Structure
3. Software Requirements and Dependencies
4. Installation Instructions 
5. How to Compile and Run
6. Deployment and Execution Instructions 
7. Screenshots of app working
8. Troubleshooting notes 
   
## 1. Project Overview 
**Problem Statement:** 
You are given a real-looking 30-day record of one customer's bank
transactions. Using it, you must: 
1. Find one meaningful money problem or opportunity this customer has —
something the data clearly shows.
2. Build a small, working digital solution that helps the customer understand
or manage their money better, and creates value for the bank (PPB — Personal
and Private Banking).
**Approach**

**Analysis** 
My key findings from the dataset are as follows 
 - The Dataset is clean as there are no missing values or incomplete fields. And by clean is that the attribute values do not have to be transformed or reinterpreted  Thus Data cleaning is no necessary.
 - Then transaction history indicates that the client has a budgeting problem (They had no debts at the beginning of the month after payday as the account balance was R42 000. At the the end of the month their cheque account went into overdraft of R2 200.
 - Each Account transaction belongs to a specific category.
 - The JSON and xlsx files are identical. This was confirmed through visual inspection and from one of the stakeholders (Mr Trevor Mavuhlele)
 - Dataset is small (less than 50 records)
 - Two transactions could be fraudulent based off the human analysis, they do not match the account owners behavior and purchasing history. These transaction will be flagged.
 - The customer could save a significant amount of money if they were to signup for a rewards program because their behavior indicates that they shop at only particular shops. For example Groceries are bought at Woolworths exclusively   
   
**Approach** 
- Create a Gamified budget manager app that has different savings tiers. It is supposed to encourage the customer to save and budget better whilst also reffering them to Standard Banks UCount rewards program.
- For example since Woolworths is a UCount rewards retailer the App will suggest how much they could save by signing up with UCount rewards by showing the saving calculations.
- The customer will reach a savings goal each month that will be displayed as achievement badges and UCount reedemable points.
- Due to time constraints the MVP will be a TKflinker and customTKinter Python GUI.
- The app is intended to be a consolidation of the Standard bank Budget Manager and UCount Rewards scheme.
- Potentially the app could suggest different account tiers and promote that to the customer. From the transaction dataset they have a Achieva account and banking fees (R120) but with the income they earn R45 000 they could qualify for a Prestige Banking Account or  Professional Banking Account. This recommendation will be rule based.   
**Dataset** 
## 2. File Structure  

## 3. Software Requirements and Dependencies 

The following table lists the runtime requirements of the project: 
| Software/Dependency | Minimum Version|  Development version | Relevance |
| -------- | -------- | -------- | 
| Python   | 3.1  |  3.1.2 | Programming language of the  
## 4. Installation Instructions 

## 5. How to Compile and Run 

## 6. Deployment and Execution Instructions 

## 7. Screenshots of app working 

## 8. Troubleshooting notes 




